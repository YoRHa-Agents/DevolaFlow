"""The single writer for every risk-parking surface (v24.0.0).

Design ref: `.local/research/v24.0.0_design_adr.md` §5.

Every mutation in this module performs three steps as one operation: write
the artifact, append the corresponding ledger row, and re-render the
generated views. There is intentionally no public path that does one without
the others, because the historical failure mode this domain replaces was
exactly a ledger and a narrative view drifting apart until neither could be
trusted.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from devolaflow.parking.models import (
    EVENT_JUDGMENT_RECORDED,
    EVENT_QUESTION_RAISED,
    EVENT_RISK_ARCHIVED,
    EVENT_RISK_OPENED,
    EVENT_RISK_STATE_CHANGED,
    EVENT_RISK_UPDATED,
    JUDGE_VIEW_MARKER,
    RISK_ID_RE,
    RISK_INDEX_MARKER,
    Judgment,
    ParkingError,
    ParkingEvent,
    ParkingSnapshot,
    Risk,
    RiskState,
    Severity,
    validate_transition,
)
from devolaflow.parking.render import render_index, render_judge_view
from devolaflow.workspace_ledger import (
    Finding,
    LedgerError,
    append_ledger_row,
    atomic_write_text,
    has_symlink_component,
    load_ledger_rows,
    utc_now,
    write_generated_view,
)

PARKING_DIRNAME = "parking"
RISKS_DIRNAME = "risks"
JUDGMENTS_FILENAME = "judgments.yaml"
EVENTS_FILENAME = "events.yaml"
INDEX_FILENAME = "INDEX.md"
JUDGE_FILENAME = "judge.md"

_FRONTMATTER_FENCE = "---"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split a risk file into its frontmatter mapping and Markdown body."""

    if not text.startswith(_FRONTMATTER_FENCE):
        raise ParkingError("risk file does not start with a frontmatter fence")
    parts = text.split(f"\n{_FRONTMATTER_FENCE}\n", 1)
    if len(parts) != 2:
        raise ParkingError("risk file frontmatter is not terminated")
    header = parts[0][len(_FRONTMATTER_FENCE) :]
    try:
        data = yaml.safe_load(header) or {}
    except yaml.YAMLError as exc:
        raise ParkingError(f"risk frontmatter is malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ParkingError("risk frontmatter is not a mapping")
    return data, parts[1]


def _render_risk(risk: Risk) -> str:
    """Serialize a risk back to frontmatter plus body."""

    header = yaml.safe_dump(
        risk.frontmatter(),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    body = risk.body if risk.body.endswith("\n") or not risk.body else risk.body + "\n"
    return f"{_FRONTMATTER_FENCE}\n{header}{_FRONTMATTER_FENCE}\n{body}"


class ParkingStore:
    """Owns `<folder>/parking/` and is the only surface permitted to write it."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self.root = self.folder / PARKING_DIRNAME

    # -- paths ---------------------------------------------------------

    @property
    def risks_dir(self) -> Path:
        """Return the directory holding one Markdown file per risk."""

        return self.root / RISKS_DIRNAME

    @property
    def judgments_path(self) -> Path:
        """Return the append-only judgment ledger path."""

        return self.root / JUDGMENTS_FILENAME

    @property
    def events_path(self) -> Path:
        """Return the append-only event ledger path."""

        return self.root / EVENTS_FILENAME

    @property
    def index_path(self) -> Path:
        """Return the generated active-risk index path."""

        return self.root / INDEX_FILENAME

    @property
    def judge_path(self) -> Path:
        """Return the generated judgment view path."""

        return self.root / JUDGE_FILENAME

    @property
    def exists(self) -> bool:
        """Return whether this folder has a parking surface at all."""

        return self.root.is_dir()

    # -- scaffold ------------------------------------------------------

    def scaffold(self) -> tuple[Path, ...]:
        """Create the parking surface as part of the first artifact batch.

        Returns every path created. Re-running is a no-op for paths that
        already exist, so a caller may safely call this on an older folder to
        backfill the surface.
        """

        created: list[Path] = []
        for directory in (self.root, self.risks_dir):
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        for path in (self.judgments_path, self.events_path):
            if not path.exists():
                path.touch()
                created.append(path)
        findings = self.render_views()
        if findings:
            raise ParkingError(
                "parking scaffold could not render its generated views: "
                + "; ".join(f"{item.code}: {item.message}" for item in findings)
            )
        created.extend(path for path in (self.index_path, self.judge_path) if path.exists())
        return tuple(created)

    # -- reads ---------------------------------------------------------

    def load_risk(self, risk_id: str) -> Risk:
        """Load one risk by id, raising when it is absent or malformed."""

        path = self.risk_path(risk_id)
        if not path.exists():
            raise ParkingError(f"risk not found: {risk_id}")
        data, body = _split_frontmatter(path.read_text(encoding="utf-8"))
        try:
            return Risk(
                id=str(data["id"]),
                title=str(data["title"]),
                state=RiskState(str(data["state"])),
                severity=Severity(str(data["severity"])),
                trigger=str(data.get("trigger", "")),
                disposition=str(data.get("disposition", "")),
                opened_at=str(data["opened_at"]),
                updated_at=str(data.get("updated_at", data["opened_at"])),
                judgment_refs=tuple(str(ref) for ref in data.get("judgment_refs") or ()),
                legacy_id=(None if data.get("legacy_id") is None else str(data["legacy_id"])),
                body=body,
            )
        except (KeyError, ValueError) as exc:
            raise ParkingError(f"risk {risk_id} has invalid frontmatter: {exc}") from exc

    def risk_path(self, risk_id: str) -> Path:
        """Return the canonical file path for a risk id."""

        if not RISK_ID_RE.match(risk_id):
            raise ParkingError(f"malformed risk id: {risk_id!r} (expected RISK-NNN)")
        return self.risks_dir / f"{risk_id}.md"

    def list_risks(self) -> tuple[Risk, ...]:
        """Load every risk in id order."""

        if not self.risks_dir.is_dir():
            return ()
        risks = []
        for path in sorted(self.risks_dir.glob("RISK-*.md")):
            risks.append(self.load_risk(path.stem))
        return tuple(risks)

    def list_judgments(self) -> tuple[Judgment, ...]:
        """Load the judgment ledger in sequence order."""

        rows = load_ledger_rows(
            self.judgments_path, required_fields=("sequence", "id", "question", "subject")
        )
        return tuple(
            Judgment(
                sequence=int(row["sequence"]),
                id=str(row["id"]),
                question=str(row["question"]),
                subject=str(row["subject"]),
                raised_at=str(row.get("raised_at", "")),
                decision=(None if row.get("decision") is None else str(row["decision"])),
                decided_at=(None if row.get("decided_at") is None else str(row["decided_at"])),
                supersedes=(None if row.get("supersedes") is None else str(row["supersedes"])),
            )
            for row in sorted(rows, key=lambda item: int(item["sequence"]))
        )

    def list_events(self) -> tuple[ParkingEvent, ...]:
        """Load the event ledger in sequence order."""

        rows = load_ledger_rows(
            self.events_path, required_fields=("sequence", "event", "subject", "timestamp")
        )
        return tuple(
            ParkingEvent(
                sequence=int(row["sequence"]),
                event=str(row["event"]),
                subject=str(row["subject"]),
                detail=str(row.get("detail", "")),
                timestamp=str(row["timestamp"]),
            )
            for row in sorted(rows, key=lambda item: int(item["sequence"]))
        )

    def snapshot(self) -> ParkingSnapshot:
        """Return one consistent read of all three parking surfaces."""

        return ParkingSnapshot(
            risks=self.list_risks(),
            judgments=self.list_judgments(),
            events=self.list_events(),
        )

    # -- writes --------------------------------------------------------

    def _next_risk_id(self) -> str:
        existing = [risk.id for risk in self.list_risks()]
        highest = max((int(rid.split("-", 1)[1]) for rid in existing), default=0)
        return f"RISK-{highest + 1:03d}"

    def _next_judgment_id(self) -> str:
        existing = self.list_judgments()
        highest = max((int(row.id.split("-", 1)[1]) for row in existing), default=0)
        return f"J-{highest + 1:03d}"

    def _append_event(self, event: str, subject: str, detail: str) -> None:
        append_ledger_row(
            self.events_path,
            {"event": event, "subject": subject, "detail": detail, "timestamp": utc_now()},
            required_fields=("event", "subject", "timestamp"),
        )

    def _write_risk(self, risk: Risk) -> None:
        path = self.risk_path(risk.id)
        if has_symlink_component(self.root, path) or path.is_symlink():
            raise ParkingError(f"refusing to write through a symlink: {risk.id}")
        atomic_write_text(path, _render_risk(risk))

    def open_risk(
        self,
        title: str,
        *,
        severity: Severity | str = Severity.MAJOR,
        trigger: str = "",
        disposition: str = "",
        body: str = "",
        legacy_id: str | None = None,
        risk_id: str | None = None,
        opened_at: str | None = None,
    ) -> Risk:
        """Register a new risk, append its event, and re-render the views."""

        if not title.strip():
            raise ParkingError("risk title must not be empty")
        self.scaffold()
        now = opened_at or utc_now()
        risk = Risk(
            id=risk_id or self._next_risk_id(),
            title=title.strip(),
            state=RiskState.OPEN,
            severity=Severity(severity),
            trigger=trigger,
            disposition=disposition,
            opened_at=now,
            updated_at=now,
            legacy_id=legacy_id,
            body=body,
        )
        if self.risk_path(risk.id).exists():
            raise ParkingError(f"risk already exists: {risk.id}")
        self._write_risk(risk)
        self._append_event(EVENT_RISK_OPENED, risk.id, risk.title)
        self._require_clean_render()
        return risk

    def transition_risk(self, risk_id: str, target: RiskState | str, *, reason: str) -> Risk:
        """Move a risk to a new lifecycle state, refusing illegal transitions."""

        if not reason.strip():
            raise ParkingError("a state transition must carry a reason")
        risk = self.load_risk(risk_id)
        target_state = RiskState(target)
        validate_transition(risk.state, target_state)
        now = utc_now()
        updated = replace(
            risk,
            state=target_state,
            updated_at=now,
            body=_append_history(
                risk.body, now, f"{risk.state.value} → {target_state.value}: {reason}"
            ),
        )
        self._write_risk(updated)
        self._append_event(
            EVENT_RISK_STATE_CHANGED,
            risk_id,
            f"{risk.state.value} -> {target_state.value}: {reason}",
        )
        self._require_clean_render()
        return updated

    def update_risk(
        self,
        risk_id: str,
        *,
        note: str,
        disposition: str | None = None,
        trigger: str | None = None,
    ) -> Risk:
        """Append an in-place history note and optionally refresh the header."""

        if not note.strip():
            raise ParkingError("a risk update must carry a note")
        risk = self.load_risk(risk_id)
        now = utc_now()
        updated = replace(
            risk,
            disposition=risk.disposition if disposition is None else disposition,
            trigger=risk.trigger if trigger is None else trigger,
            updated_at=now,
            body=_append_history(risk.body, now, note),
        )
        self._write_risk(updated)
        self._append_event(EVENT_RISK_UPDATED, risk_id, note)
        self._require_clean_render()
        return updated

    def raise_question(self, question: str, *, subject: str) -> Judgment:
        """Queue a decision for the operator without blocking the risk."""

        if not question.strip():
            raise ParkingError("a question must not be empty")
        self.scaffold()
        judgment_id = self._next_judgment_id()
        now = utc_now()
        row = append_ledger_row(
            self.judgments_path,
            {
                "id": judgment_id,
                "question": question.strip(),
                "subject": subject,
                "raised_at": now,
                "decision": None,
                "decided_at": None,
                "supersedes": None,
            },
            required_fields=("id", "question", "subject"),
            unique_fields=("id",),
        )
        self._append_event(EVENT_QUESTION_RAISED, subject, question.strip())
        if RISK_ID_RE.match(subject) and self.risk_path(subject).exists():
            self._link_judgment(subject, judgment_id)
        self._require_clean_render()
        return Judgment(
            sequence=int(row["sequence"]),
            id=judgment_id,
            question=question.strip(),
            subject=subject,
            raised_at=now,
        )

    def record_decision(
        self,
        decision: str,
        *,
        question_id: str | None = None,
        subject: str | None = None,
        question: str | None = None,
    ) -> Judgment:
        """Append a decision row; answering a question never edits it.

        Either answer a queued question by id, or record a standalone
        decision by supplying ``subject`` and ``question``.
        """

        if not decision.strip():
            raise ParkingError("a decision must not be empty")
        self.scaffold()
        existing = {row.id: row for row in self.list_judgments()}
        if question_id is not None:
            prior = existing.get(question_id)
            if prior is None:
                raise ParkingError(f"unknown judgment id: {question_id}")
            question_text = prior.question
            subject_value = prior.subject
        else:
            if subject is None or question is None:
                raise ParkingError("a standalone decision requires subject and question")
            question_text = question.strip()
            subject_value = subject
        judgment_id = self._next_judgment_id()
        now = utc_now()
        row = append_ledger_row(
            self.judgments_path,
            {
                "id": judgment_id,
                "question": question_text,
                "subject": subject_value,
                "raised_at": now,
                "decision": decision.strip(),
                "decided_at": now,
                "supersedes": question_id,
            },
            required_fields=("id", "question", "subject"),
            unique_fields=("id",),
        )
        self._append_event(EVENT_JUDGMENT_RECORDED, subject_value, decision.strip())
        if RISK_ID_RE.match(subject_value) and self.risk_path(subject_value).exists():
            self._link_judgment(subject_value, judgment_id)
        self._require_clean_render()
        return Judgment(
            sequence=int(row["sequence"]),
            id=judgment_id,
            question=question_text,
            subject=subject_value,
            raised_at=now,
            decision=decision.strip(),
            decided_at=now,
            supersedes=question_id,
        )

    def _link_judgment(self, risk_id: str, judgment_id: str) -> None:
        risk = self.load_risk(risk_id)
        if judgment_id in risk.judgment_refs:
            return
        self._write_risk(
            replace(risk, judgment_refs=(*risk.judgment_refs, judgment_id), updated_at=utc_now())
        )

    def record_archival(self, risk_id: str, destination: str) -> None:
        """Record that compaction relocated a closed risk's file.

        Called after the move has already happened, so the risk file is
        expected to be absent from `risks/`. The event ledger is the durable
        record of the transition; the relocated file still carries its own
        `state: closed` frontmatter and is reachable through the mapping
        ledger.
        """

        if not RISK_ID_RE.match(risk_id):
            raise ParkingError(f"malformed risk id: {risk_id!r}")
        self._append_event(EVENT_RISK_ARCHIVED, risk_id, destination)
        self._require_clean_render()

    def mark_archived(self, risk_id: str, destination: str) -> Risk:
        """Validate and apply the archived transition while the file is present."""

        risk = self.load_risk(risk_id)
        validate_transition(risk.state, RiskState.ARCHIVED)
        self._append_event(EVENT_RISK_ARCHIVED, risk_id, destination)
        return replace(risk, state=RiskState.ARCHIVED)

    # -- generated views -----------------------------------------------

    def render_views(self) -> tuple[Finding, ...]:
        """Re-render both generated views from the authoritative ledgers."""

        snapshot = self.snapshot()
        findings: list[Finding] = []
        findings.extend(
            write_generated_view(
                self.root,
                self.index_path,
                render_index(snapshot),
                marker=RISK_INDEX_MARKER,
            )
        )
        findings.extend(
            write_generated_view(
                self.root,
                self.judge_path,
                render_judge_view(snapshot),
                marker=JUDGE_VIEW_MARKER,
            )
        )
        return tuple(findings)

    def _require_clean_render(self) -> None:
        findings = self.render_views()
        if findings:
            raise ParkingError(
                "parking views could not be re-rendered: "
                + "; ".join(f"{item.code}: {item.message}" for item in findings)
            )

    def audit(self) -> tuple[Finding, ...]:
        """Report drift between the ledgers and the generated views."""

        from devolaflow.workspace_ledger import detect_view_drift

        try:
            snapshot = self.snapshot()
        except (LedgerError, ParkingError) as exc:
            from devolaflow.workspace_ledger import finding as make_finding

            return (make_finding("PARKING_UNREADABLE", str(exc)),)
        findings: list[Finding] = []
        findings.extend(
            detect_view_drift(
                self.root, self.index_path, render_index(snapshot), marker=RISK_INDEX_MARKER
            )
        )
        findings.extend(
            detect_view_drift(
                self.root, self.judge_path, render_judge_view(snapshot), marker=JUDGE_VIEW_MARKER
            )
        )
        return tuple(findings)


def _append_history(body: str, timestamp: str, note: str) -> str:
    """Append one dated history bullet, creating the section on first use."""

    heading = "## History"
    entry = f"- {timestamp} — {note}"
    text = body.rstrip("\n")
    if heading not in text:
        text = f"{text}\n\n{heading}\n\n{entry}" if text else f"{heading}\n\n{entry}"
    else:
        text = f"{text}\n{entry}"
    return text + "\n"


__all__ = [
    "EVENTS_FILENAME",
    "INDEX_FILENAME",
    "JUDGE_FILENAME",
    "JUDGMENTS_FILENAME",
    "PARKING_DIRNAME",
    "RISKS_DIRNAME",
    "ParkingStore",
]
