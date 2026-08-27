"""Focused implementation slice for the legacy module."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _check_preflight(
    text: str,
    *,
    change_id: str,
    checklist_ids: set[str] | None,
    repo_root: Path,
    archived: bool,
    report: BudgetReport,
) -> None:
    """Validate canonical Sections 0–3, mirror bytes, and authorization seal."""
    try:
        frontmatter, sections = _extract_preflight_sections(text)
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_SECTION_ORDER", str(exc))
        )
        return

    try:
        _frontmatter_shape(frontmatter, change_id=change_id)
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_AUTHORIZATION", str(exc))
        )

    authorized_at = frontmatter.get("authorized_at")
    config_hash = frontmatter.get("project_config_hash")
    authorization_hash = frontmatter.get("authorization_hash")

    authorization_valid = authorized_at is None
    if authorized_at is not None:
        try:
            _validate_timestamp(authorized_at, field_name="authorized_at")
            authorization_valid = True
        except PreflightAuthorizationError:
            authorization_valid = False
    hash_valid = config_hash is None or (
        isinstance(config_hash, str) and _SHA256_RE.fullmatch(config_hash)
    )
    seal_valid = authorization_hash is None or (
        isinstance(authorization_hash, str) and _SHA256_RE.fullmatch(authorization_hash)
    )
    if not authorization_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_AUTHORIZATION",
                "authorized_at must be null or an ISO-8601 UTC timestamp",
            )
        )
    if not hash_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_HASH",
                "project_config_hash must be null or 64 lowercase hexadecimal characters",
            )
        )
    if not seal_valid:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "authorization_hash must be null or 64 lowercase hexadecimal characters",
            )
        )
    if authorized_at is not None and authorization_valid and config_hash is None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_AUTHORIZATION",
                "a signed preflight requires project_config_hash",
            )
        )
    if authorized_at is not None and authorization_valid and authorization_hash is None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "a signed preflight requires authorization_hash",
            )
        )
    if authorized_at is None and config_hash is not None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_HASH",
                "an unsigned preflight must not retain project_config_hash",
            )
        )
    if authorized_at is None and authorization_hash is not None:
        report.violations.append(
            SemanticViolation(
                "preflight.md",
                "PREFLIGHT_SEAL",
                "an unsigned preflight must not retain authorization_hash",
            )
        )

    section0_state = None
    try:
        section0_state = _validate_section0(sections.contents[0], frontmatter)
    except PreflightAuthorizationError as exc:
        report.violations.append(SemanticViolation("preflight.md", "PREFLIGHT_SECTION_0", str(exc)))

    cards = None
    try:
        cards = _parse_stop_cards(
            sections.contents[1],
            checklist_ids=checklist_ids,
        )
    except PreflightAuthorizationError as exc:
        report.violations.append(SemanticViolation("preflight.md", "PREFLIGHT_STOP_CARD", str(exc)))

    if cards is not None and authorization_valid:
        try:
            _parse_authorization_records(
                sections.contents[2],
                cards=cards,
                authorized_at=authorized_at,
            )
        except PreflightAuthorizationError as exc:
            report.violations.append(
                SemanticViolation("preflight.md", "PREFLIGHT_AUTHORIZATION", str(exc))
            )

    try:
        _validate_permitted_stops(sections.contents[3])
    except PreflightAuthorizationError as exc:
        report.violations.append(
            SemanticViolation("preflight.md", "PREFLIGHT_PERMITTED_STOPS", str(exc))
        )

    expected_mirror_hash = config_hash
    if section0_state is not None and section0_state.inherited_hash is not None:
        expected_mirror_hash = section0_state.inherited_hash
    if (
        section0_state is not None
        and section0_state.config is not None
        and config_hash is not None
        and hash_valid
    ):
        compiled_hash = hashlib.sha256(
            _deterministic_mirror_bytes(section0_state.config)
        ).hexdigest()
        if compiled_hash != config_hash:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_HASH",
                    "project_config_hash does not match deterministic full Section 0 YAML",
                )
            )

    if (
        not archived
        and isinstance(expected_mirror_hash, str)
        and _SHA256_RE.fullmatch(expected_mirror_hash)
    ):
        mirror = repo_root / ".local" / "project_config.yaml"
        try:
            mirror_digest = hashlib.sha256(mirror.read_bytes()).hexdigest()
        except OSError:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_HASH",
                    "active project configuration mirror is missing or unreadable",
                )
            )
        else:
            if mirror_digest != expected_mirror_hash:
                report.violations.append(
                    SemanticViolation(
                        "preflight.md",
                        "PREFLIGHT_HASH",
                        "project_config_hash does not match raw .local/project_config.yaml bytes",
                    )
                )

    if (
        authorized_at is not None
        and authorization_valid
        and config_hash is not None
        and hash_valid
        and authorization_hash is not None
        and seal_valid
    ):
        expected_seal = _authorization_digest(frontmatter, sections)
        if authorization_hash != expected_seal:
            report.violations.append(
                SemanticViolation(
                    "preflight.md",
                    "PREFLIGHT_SEAL",
                    "authorization_hash does not match signed Sections 0 through 3",
                )
            )


def _resolve_harness_reference(
    reference: str,
    *,
    change_folder: Path,
    repo_root: Path,
) -> Path | None:
    """Resolve a change- or repo-relative reference to an existing regular file."""
    for base in (change_folder, repo_root):
        candidate = base / reference
        if candidate.is_file():
            return candidate
    return None


def _check_harness_reference(
    frontmatter: dict[str, object],
    field_name: str,
    kind: str,
    *,
    nullable: bool,
    change_folder: Path,
    repo_root: Path,
    report: BudgetReport,
    filename: str = HARNESS_PREFLIGHT_FILENAME,
) -> None:
    """Validate one frontmatter path reference of a harness artifact."""
    if field_name not in frontmatter:
        return  # Missing key already reported as HPF_FRONTMATTER.
    value = frontmatter[field_name]
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value:
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} must be a non-empty change- or repo-relative path"
                + (" or null" if nullable else ""),
            )
        )
        return
    if Path(value).is_absolute():
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} must be a relative path (S-2), got {value!r}",
            )
        )
        return
    if _resolve_harness_reference(value, change_folder=change_folder, repo_root=repo_root) is None:
        report.violations.append(
            SemanticViolation(
                filename,
                kind,
                f"{field_name} {value!r} does not exist relative to the change "
                "folder or the repo root",
            )
        )


def _check_harness_preflight(
    change_folder: Path,
    *,
    repo_root: Path,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the OPTIONAL ``harness_preflight.md`` artifact when present.

    Absence produces zero findings — the change is simply not
    harness-flagged (artifact-as-contract per
    ``schemas/agent-workspace/harness-preflight.yaml#presence_semantics``).
    """
    result = _read_artifact(change_folder, HARNESS_PREFLIGHT_FILENAME, report, cache)
    if result.state == "missing":
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact (S-5).

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename=HARNESS_PREFLIGHT_FILENAME)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(
            SemanticViolation(HARNESS_PREFLIGHT_FILENAME, "HPF_FRONTMATTER", exc.message)
        )
        return

    frontmatter = artifact.frontmatter
    missing = [key for key in _HARNESS_PREFLIGHT_REQUIRED_KEYS if key not in frontmatter]
    if missing:
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_FRONTMATTER",
                f"frontmatter is missing required key(s): {', '.join(missing)}",
            )
        )

    if "schema_version" in frontmatter and not _strict_frontmatter_equal(
        frontmatter["schema_version"], 1
    ):
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_SCHEMA_VERSION",
                f"schema_version={frontmatter['schema_version']!r}; the only "
                "supported version is 1",
            )
        )

    headings = [
        line.rstrip()
        for line in artifact.body.splitlines()
        if _HARNESS_NUMBERED_HEADING_RE.match(line)
    ]
    if headings != list(_HARNESS_PREFLIGHT_HEADINGS):
        report.violations.append(
            SemanticViolation(
                HARNESS_PREFLIGHT_FILENAME,
                "HPF_SECTION_ORDER",
                "numbered '## N.' headings must be exactly "
                f"{list(_HARNESS_PREFLIGHT_HEADINGS)} in order; got {headings}",
            )
        )

    _check_harness_reference(
        frontmatter,
        "gap_report",
        "HPF_GAP_REPORT",
        nullable=False,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
    )
    _check_harness_reference(
        frontmatter,
        "axes_config",
        "HPF_AXES_CONFIG",
        nullable=True,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
    )


def _pathfinder_value_is_empty(value: str) -> bool:
    """Return whether a scalar Pathfinder field has no meaningful value."""
    return value.strip().strip("\"'") in {"", "null", "None", "[]", "{}"}


def _check_pathfinder_report(
    change_folder: Path,
    *,
    repo_root: Path,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the OPTIONAL Pathfinder report when present.

    Absence is a clean no-op: only a dispatched Pathfinder task creates this
    artifact.  A present report is fail-closed because its contract is the
    evidence consumed by later waves.
    """
    result = _read_artifact(change_folder, PATHFINDER_REPORT_FILENAME, report, cache)
    if result.state == "missing":
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact (S-5).

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename=PATHFINDER_REPORT_FILENAME)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(
            SemanticViolation(PATHFINDER_REPORT_FILENAME, "PFR_FRONTMATTER", exc.message)
        )
        return

    frontmatter = artifact.frontmatter
    missing = [key for key in _PATHFINDER_REQUIRED_KEYS if key not in frontmatter]
    if missing:
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_FRONTMATTER",
                f"frontmatter is missing required key(s): {', '.join(missing)}",
            )
        )

    schema_version = frontmatter.get("schema_version")
    if not _strict_frontmatter_equal(schema_version, 1):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_SCHEMA_VERSION",
                f"schema_version={schema_version!r}; the only supported version is 1",
            )
        )

    scan_mode = frontmatter.get("scan_mode")
    scan_round = frontmatter.get("scan_round")
    if (
        not isinstance(scan_mode, str)
        or scan_mode not in _PATHFINDER_SCAN_MODES
        or not isinstance(scan_round, int)
        or isinstance(scan_round, bool)
        or scan_round < 1
    ):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_FRONTMATTER",
                "scan_mode must be initial/incremental and scan_round must be "
                "an integer greater than or equal to 1",
            )
        )

    body_lines = artifact.body.splitlines()
    heading_positions = [
        next((index for index, line in enumerate(body_lines) if line == heading), -1)
        for heading in _PATHFINDER_HEADINGS
    ]
    if (
        any(position < 0 for position in heading_positions)
        or len(set(heading_positions)) != len(_PATHFINDER_HEADINGS)
        or heading_positions != sorted(heading_positions)
    ):
        report.violations.append(
            SemanticViolation(
                PATHFINDER_REPORT_FILENAME,
                "PFR_SECTION_ORDER",
                f"required headings must appear once in order: {list(_PATHFINDER_HEADINGS)}",
            )
        )

    _check_harness_reference(
        frontmatter,
        "gap_report",
        "PFR_GAP_REPORT",
        nullable=False,
        change_folder=change_folder,
        repo_root=repo_root,
        report=report,
        filename=PATHFINDER_REPORT_FILENAME,
    )

    in_findings_or_handoff = False
    for line in body_lines:
        if line.startswith("## "):
            in_findings_or_handoff = line in {"## Findings", "## Handoff"}
        if in_findings_or_handoff and re.search(r"\b(?:evidence|artifact_path)\s*:", line):
            field_value = line.split(":", 1)[1]
            if _PATHFINDER_ABSOLUTE_PATH_RE.search(field_value):
                report.violations.append(
                    SemanticViolation(
                        PATHFINDER_REPORT_FILENAME,
                        "PFR_ABSOLUTE_PATH",
                        "evidence and handoff paths must be relative (S-2)",
                    )
                )
                break

    for block in _PATHFINDER_FINDING_START_RE.split(artifact.body)[1:]:
        if not _PATHFINDER_SEVERITY_BLOCKER_RE.search(block):
            continue
        signal = _PATHFINDER_ACCEPTANCE_SIGNAL_RE.search(block)
        if signal is None or _pathfinder_value_is_empty(signal.group(1)):
            report.violations.append(
                SemanticViolation(
                    PATHFINDER_REPORT_FILENAME,
                    "PFR_BLOCKER_SIGNAL",
                    "every BLOCKER finding must include a non-empty acceptance_signal",
                )
            )


def _entrance_expected_inventory() -> set[str]:
    """Section 3 parity target (design D-7).

    The budget registry keys minus the router itself, plus the ``evidence/``
    directory (byte-limited rather than token-budgeted, but still part of the
    artifact set an onboarding agent must know about).
    """
    return (set(CHECKLIST_ARTIFACT_BUDGETS) - {"entrance.md"}) | {"evidence/"}


def _check_entrance(
    change_folder: Path,
    *,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Validate the entrance.md onboarding router (change-entrance schema).

    A missing file yields ``ENTRANCE_MISSING`` at WARN severity — pre-v17.2
    folders are backfilled on first resume (design D-4), so absence must not
    flip the lint exit code. A present-but-malformed file fails loud (S-5).
    """
    result = _read_artifact(change_folder, "entrance.md", report, cache)
    if result.state == "missing":
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_MISSING",
                "agent onboarding entry point is absent; backfill from the "
                "scaffold template (schemas/agent-workspace/change-entrance.yaml)",
                severity="WARN",
            )
        )
        return
    if result.text is None:
        return  # READ_ERROR already recorded by _read_artifact.

    try:
        artifact = round_parser.parse_frontmatter(result.text, filename="entrance.md")
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation("entrance.md", exc.kind, exc.message))
        return

    frontmatter = artifact.frontmatter or {}
    if frontmatter.get("parent") != report.change_id:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_PARENT",
                f"frontmatter parent {frontmatter.get('parent')!r} must equal "
                f"the change-id {report.change_id!r}",
            )
        )
    if frontmatter.get("schema_version") != 1:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_SCHEMA_VERSION",
                f"schema_version must be 1 (got {frontmatter.get('schema_version')!r})",
            )
        )

    lines = artifact.body.splitlines()
    for heading in _ENTRANCE_REQUIRED_HEADINGS:
        if heading not in lines:
            report.violations.append(
                SemanticViolation(
                    "entrance.md",
                    "ENTRANCE_SECTION",
                    f"required section heading {heading!r} is absent",
                )
            )

    if _ENTRANCE_INVENTORY_HEADING not in lines:
        return  # ENTRANCE_SECTION already recorded; parity has no anchor.

    listed: set[str] = set()
    in_inventory = False
    for line in lines:
        if line.startswith("## "):
            in_inventory = line == _ENTRANCE_INVENTORY_HEADING
            continue
        if in_inventory:
            match = _ENTRANCE_INVENTORY_ROW_RE.match(line)
            if match is not None:
                listed.add(match.group(1))
    expected = _entrance_expected_inventory()
    if listed != expected:
        report.violations.append(
            SemanticViolation(
                "entrance.md",
                "ENTRANCE_PARITY",
                "Section 3 inventory drifted from the budget registry — "
                f"missing {sorted(expected - listed)!r}, "
                f"surplus {sorted(listed - expected)!r}",
            )
        )


def _lint_checklist_semantics(
    change_folder: Path,
    *,
    repo_root: Path,
    archived: bool,
    report: BudgetReport,
    cache: dict[str, _ReadResult],
) -> None:
    """Run the four v16 semantic check families with dependency gating."""
    goal = _parse_markdown_frontmatter(
        "goal.md",
        _read_artifact(change_folder, "goal.md", report, cache),
        report,
    )
    checklist = _parse_markdown_frontmatter(
        "checklist.md",
        _read_artifact(change_folder, "checklist.md", report, cache),
        report,
    )
    preflight_result = _read_artifact(change_folder, "preflight.md", report, cache)
    preflight = _parse_markdown_frontmatter("preflight.md", preflight_result, report)

    goal_entries = _goal_entries(goal.body, report) if goal is not None else None
    checklist_headings = (
        _checklist_goal_headings(checklist.body, report) if checklist is not None else None
    )
    if (
        goal_entries is not None
        and checklist_headings is not None
        and goal_entries != checklist_headings
    ):
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "GOAL_ALIGNMENT",
                f"goal entries {goal_entries!r} do not equal checklist headings "
                f"{checklist_headings!r}",
            )
        )

    if goal is not None and goal.frontmatter is not None and goal_entries is not None:
        _check_derived_field(
            "goal.md",
            goal.frontmatter,
            "goals_count",
            len(goal_entries),
            report,
        )

    items = _checklist_items(checklist.body, report) if checklist is not None else None
    if items is not None:
        if checklist is not None and checklist.frontmatter is not None:
            priority_dist = {
                priority: sum(item.priority == priority for item in items)
                for priority in ("P0", "P1", "P2")
            }
            reverted_open = sum(
                not item.checked
                and any(line.startswith("      reverted:") for line in item.metadata)
                for item in items
            )
            for field_name, expected in (
                ("total_items", len(items)),
                ("checked", sum(item.checked for item in items)),
                ("priority_dist", priority_dist),
                ("reverted_open", reverted_open),
            ):
                _check_derived_field(
                    "checklist.md",
                    checklist.frontmatter,
                    field_name,
                    expected,
                    report,
                )
        _check_evidence_paths(change_folder, items, report)
        if checklist is not None:
            stage_result = _read_artifact(change_folder, "stage.md", report, cache)
            _check_progress_header(checklist.body, items, stage_result.text, report)

    if preflight is not None and preflight_result.text is not None:
        _check_preflight(
            preflight_result.text,
            change_id=report.change_id,
            checklist_ids={item.item_id for item in items} if items is not None else None,
            repo_root=repo_root,
            archived=archived,
            report=report,
        )

    _check_entrance(change_folder, report=report, cache=cache)


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
