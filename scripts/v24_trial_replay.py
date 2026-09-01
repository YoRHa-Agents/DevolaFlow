#!/usr/bin/env python3
"""v24.0.0 trial replay — static replay of the real v2.8.6 risk-parking sample.

Takes the 217-line production artifact that motivated this cycle, adopts it
into the structured parking surface, compacts the original out of the reading
path, and measures four things the cycle's acceptance criteria name:

1. resident-token reduction (target >= 70%);
2. zero loss, proved by re-hashing every archived original;
3. restore cost — tokens an agent reads to answer a historical question,
   versus reading the source outright;
4. every legacy identifier surviving verbatim.

Writes a JSON reading to `.local/research/v24.0.0/trial_replay.json`. Report
only: it operates on a scratch copy and never modifies the sample.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from devolaflow.parking import ParkingStore, plan_adoption  # noqa: E402
from devolaflow.parking.adopt import apply_adoption  # noqa: E402
from devolaflow.workspace_compact import (  # noqa: E402
    apply_plan,
    build_plan,
    load_mappings,
    locate,
    measure_file,
    resident_tokens,
    verify_integrity,
)
from devolaflow.workspace_compact.engine import archived_root  # noqa: E402

SAMPLE = Path(".local/tasks/add_compact_and_new_files/sample-risk-parking.md")
OUTPUT = Path(".local/research/v24.0.0/trial_replay.json")

#: Questions a real agent would ask of this document. Each names a disposition
#: buried in a specific row; answering it is the restore-cost probe.
QUERIES = ("PV-16b", "PV-29", "A-Q25", "phase1-restamp", "slotsregistry")


def _restore_cost(folder: Path, query: str) -> dict[str, object]:
    hits = locate(folder, query, limit=5)
    excerpt_tokens = sum(max(1, len(hit.excerpt) // 4) for hit in hits)
    return {
        "query": query,
        "hits": len(hits),
        "tokens_read": excerpt_tokens,
        "resolved": bool(hits),
        "first_hit": None if not hits else f"{hits[0].original_source}#L{hits[0].line}",
    }


def run(sample: Path, output: Path) -> dict[str, object]:
    """Execute one full adopt -> compact -> locate replay and return readings."""

    source_tokens = measure_file(sample).tokens
    source_bytes = sample.stat().st_size
    source_lines = len(sample.read_text(encoding="utf-8").splitlines())

    scratch = Path(tempfile.mkdtemp(prefix="v24-replay-"))
    folder = scratch / "v2.8.6_purified"
    folder.mkdir()
    staged = folder / sample.name
    shutil.copy2(sample, staged)

    plan = plan_adoption(staged, provenance=sample.as_posix())
    created = apply_adoption(folder, plan, approval_fingerprint=plan.fingerprint)
    store = ParkingStore(folder)
    risks = store.list_risks()

    before_tokens = resident_tokens(folder, exclude=(archived_root(folder),))
    compact_plan = build_plan(folder, include=[sample.name])
    result = apply_plan(folder, compact_plan, approval_fingerprint=compact_plan.fingerprint)
    after_tokens = resident_tokens(folder, exclude=(archived_root(folder),))

    integrity = verify_integrity(folder)
    mappings = load_mappings(folder)
    restore_costs = [_restore_cost(folder, query) for query in QUERIES]
    average_restore = (
        sum(int(item["tokens_read"]) for item in restore_costs) / len(restore_costs)
        if restore_costs
        else 0
    )

    legacy_ids = {risk.legacy_id for risk in risks if risk.legacy_id}
    source_ids = {item.legacy_id for item in plan.candidates}

    # The objective is agent reading cost, not bytes on disk. Before, finding
    # one disposition meant reading the whole blob because it had no index.
    # After, orientation is the generated index and the agent opens exactly
    # the one risk file it needs. Resident sum is reported alongside because
    # it is the honest counterweight: splitting a blob into per-risk files
    # costs total storage even as it cuts what has to be read.
    index_tokens = measure_file(store.index_path).tokens
    risk_token_counts = sorted(
        measure_file(store.risk_path(risk.id)).tokens for risk in store.list_risks()
    )
    typical_risk = risk_token_counts[len(risk_token_counts) // 2] if risk_token_counts else 0
    working_set_after = index_tokens + typical_risk

    reading: dict[str, object] = {
        "artifact_type": "v24-trial-replay",
        "schema_version": 1,
        "sample": sample.as_posix(),
        "source": {
            "lines": source_lines,
            "bytes": source_bytes,
            "tokens": source_tokens,
        },
        "adoption": {
            "candidates": len(plan.candidates),
            "risks_created": len(created),
            "narrative_lines_left_in_source": plan.unmapped_lines,
            "legacy_ids_preserved_verbatim": sorted(legacy_ids) == sorted(source_ids),
            "legacy_id_count": len(legacy_ids),
        },
        "compaction": {
            "relocated": len(result.applied),
            "resident_tokens_before": before_tokens,
            "resident_tokens_after": after_tokens,
            "reduction": round((before_tokens - after_tokens) / before_tokens, 4)
            if before_tokens
            else 0.0,
            "vs_original_source": round((source_tokens - after_tokens) / source_tokens, 4)
            if source_tokens
            else 0.0,
            "success": result.success,
            "findings": list(result.findings),
        },
        "working_set": {
            "before_tokens": source_tokens,
            "before_note": "no index existed; one disposition required reading the whole file",
            "after_tokens": working_set_after,
            "after_note": "generated index plus the one risk file the question is about",
            "index_tokens": index_tokens,
            "typical_risk_tokens": typical_risk,
            "reduction": round((source_tokens - working_set_after) / source_tokens, 4)
            if source_tokens
            else 0.0,
        },
        "zero_loss": {
            "mapping_rows": len(mappings),
            "hash_mismatches": list(integrity),
            "verified": not integrity,
        },
        "restore_cost": {
            "probes": restore_costs,
            "average_tokens_read": round(average_restore, 1),
            "source_tokens_if_read_whole": source_tokens,
            "ratio_vs_reading_source": round(average_restore / source_tokens, 4)
            if source_tokens
            else 0.0,
            "all_resolved": all(bool(item["resolved"]) for item in restore_costs),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(reading, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(scratch, ignore_errors=True)
    return reading


def main(argv: list[str] | None = None) -> int:
    """Run the replay and print its headline readings."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    if not args.sample.is_file():
        print(f"sample not found: {args.sample}", file=sys.stderr)
        return 2
    reading = run(args.sample, args.output)
    compaction = reading["compaction"]
    restore_cost = reading["restore_cost"]
    zero_loss = reading["zero_loss"]
    working_set = reading["working_set"]
    assert isinstance(compaction, dict)
    assert isinstance(restore_cost, dict)
    assert isinstance(zero_loss, dict)
    assert isinstance(working_set, dict)
    print(
        f"working set: {working_set['before_tokens']} -> {working_set['after_tokens']} "
        f"({working_set['reduction']:.1%} reduction)"
    )
    print(
        f"resident tokens: {compaction['resident_tokens_before']} -> "
        f"{compaction['resident_tokens_after']} "
        f"({compaction['reduction']:.1%} reduction)"
    )
    print(f"zero loss verified: {zero_loss['verified']} over {zero_loss['mapping_rows']} rows")
    print(
        f"restore cost: {restore_cost['average_tokens_read']} tokens avg vs "
        f"{restore_cost['source_tokens_if_read_whole']} to read the source "
        f"({restore_cost['ratio_vs_reading_source']:.1%})"
    )
    print(f"reading written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
