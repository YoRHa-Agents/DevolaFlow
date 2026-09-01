#!/usr/bin/env python
"""Register this cycle's real risks through the parking tool (v24.0.0 PV-05).

This is the dogfood round the plan calls for: the v24 development workspace
records its own risks and open questions through the surface v24 introduces,
rather than narrating them into prose that nobody can query later.

Every risk below was actually hit while building v24. Two are already closed
because they were fixed in the same cycle, which is exactly the shape compaction
is meant to exploit: a closed risk is history, and history belongs in the
archive with a pointer, not in the file an agent reads on every turn.

Re-running is safe: the script reports what already exists and exits without
appending duplicates.
"""

from __future__ import annotations

import sys
from pathlib import Path

from devolaflow.parking.store import ParkingStore

FOLDER = Path(".local/tasks/v24-workspace-compact")

RISKS: tuple[dict[str, str], ...] = (
    {
        "title": "Harness ledger aborts on a retired SI-10 gate name",
        "severity": "blocker",
        "trigger": "A gate name a previous Makefile emitted is absent from the current vocabulary",
        "disposition": (
            "Fixed: the reader accepts RETIRED_SI10_GATE_NAMES as historical evidence and warns; "
            "the writer still refuses to emit one, so the vocabulary cannot silently expand."
        ),
        "body": (
            "One `iteration-delta-gate` row made the entire harness ledger unreadable, and with "
            "it every downstream evaluation for the cycle. The blast radius, not the bad row, "
            "was the real defect: strict validation that aborts a whole append-only ledger "
            "converts a naming drift into a total outage.\n\n"
            "This finding is why compaction telemetry writes to its own ledger rather than "
            "sharing the harness one."
        ),
        "state": "closed",
    },
    {
        "title": "npm pack --json changed shape and froze the delivery contract test",
        "severity": "major",
        "trigger": "npm now returns an object keyed by package name where it once returned a list",
        "disposition": (
            "Fixed: both the test and the functional runner normalise either shape and assert on "
            "the packed file set, which is what the delivery contract actually pins."
        ),
        "body": (
            "Three tests were red on a clean tree before v24 work began. A permanently failing "
            "test is worse than no test: it trains everyone to read a red suite as normal, so "
            "the next real regression arrives disguised as the usual noise."
        ),
        "state": "closed",
    },
    {
        "title": "Per-risk file split raises total stored tokens even as it cuts reading cost",
        "severity": "major",
        "trigger": "Splitting one blob into many files adds per-file frontmatter and structure",
        "disposition": (
            "Mitigating: adoption no longer copies frontmatter fields into the body, and the "
            "accepted metric is the agent working set (index + one risk file), not the sum of "
            "bytes on disk. Resident sum is still reported so the trade-off stays visible."
        ),
        "body": (
            "Measured on the v2.8.6 sample: working set 8679 -> 1284 tokens (85.2% cut), while "
            "the resident sum fell only 39.4%. Reporting solely the flattering number would have "
            "hidden a real cost; reporting solely the resident sum would have hidden the actual "
            "benefit. Both belong in the reading."
        ),
        "state": "mitigating",
    },
    {
        "title": "Python runtime is a hard prerequisite for every parking and compact write",
        "severity": "major",
        "trigger": "A host without a usable Python runtime cannot write either surface",
        "disposition": (
            "Accepted for v24: writes report unavailable with an install command and reads stay "
            "unrestricted. Degrading to hand-written files was rejected because it reintroduces "
            "exactly the unqueryable prose this cycle exists to remove."
        ),
        "body": (
            "Long-term direction recorded in `.local/feedbacks/feedback_for_v24.md`: evaluate a "
            "Rust binary distribution so the tooling stops inheriting the host's Python problems."
        ),
        "state": "parked",
    },
    {
        "title": "Handoff envelope relocation is blocked pending an S-9 amendment",
        "severity": "minor",
        "trigger": "S-9 makes envelopes append-only with no relocation clause",
        "disposition": (
            "Parked behind a human decision. The read-only generated handoff index ships in the "
            "meantime, so the capability is useful without touching a single envelope."
        ),
        "body": (
            "The amendment draft is `.local/research/v24.0.0_s9_amendment_draft.md`. It is "
            "deliberately the narrowest form that solves the problem: only envelopes of an "
            "already-archived change qualify, relocation is tool-executed and separately "
            "approved, and no envelope is ever rewritten or deleted.\n\n"
            "Shipping the index first means the release does not depend on the decision."
        ),
        "state": "parked",
    },
)

QUESTIONS: tuple[tuple[str, str], ...] = (
    (
        "Handoff envelope relocation is blocked pending an S-9 amendment",
        "Sign the narrow S-9 amendment permitting tool-mediated relocation of already-archived "
        "handoff envelopes (append-only preserved, no rewrite, no delete, separate approval)? "
        "Draft: .local/research/v24.0.0_s9_amendment_draft.md",
    ),
    (
        "Per-risk file split raises total stored tokens even as it cuts reading cost",
        "Accept the agent working set (generated index plus one risk file) as the headline "
        "compaction metric, with resident stored tokens reported alongside as the counterweight?",
    ),
)


def main() -> int:
    """Register the cycle's risks and open questions; safe to re-run."""

    store = ParkingStore(FOLDER)
    store.scaffold()
    existing = {risk.title: risk for risk in store.list_risks()}

    subject_ids: dict[str, str] = {}
    for spec in RISKS:
        title = spec["title"]
        if title in existing:
            subject_ids[title] = existing[title].id
            print(f"exists  {existing[title].id}  {title}")
            continue
        risk = store.open_risk(
            title,
            severity=spec["severity"],
            trigger=spec["trigger"],
            disposition=spec["disposition"],
            body=spec["body"],
        )
        target = spec["state"]
        if target != "open":
            store.transition_risk(risk.id, target, reason="registered at its settled state")
        subject_ids[title] = risk.id
        print(f"opened  {risk.id}  [{target}]  {title}")

    asked = {row.question for row in store.list_judgments()}
    for subject_title, question in QUESTIONS:
        if question in asked:
            print(f"exists  question for {subject_ids.get(subject_title, subject_title)}")
            continue
        row = store.raise_question(question, subject=subject_ids[subject_title])
        print(f"asked   {row.id}  -> {row.subject}")

    snapshot = store.snapshot()
    print(
        f"\nlive={sum(1 for r in snapshot.risks if r.live)} "
        f"settled={sum(1 for r in snapshot.risks if not r.live)} "
        f"pending_decisions={len(snapshot.pending)}"
    )
    findings = store.audit()
    if findings:
        for item in findings:
            print(f"DRIFT {item.code}: {item.message}")
        return 1
    print("generated views match their ledgers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
