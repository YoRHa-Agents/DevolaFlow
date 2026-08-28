"""Focused implementation slice for artifact semantics."""

# ruff: noqa: F403, F405

from __future__ import annotations

from .common import *  # noqa: F403


def _parse_markdown_frontmatter(
    filename: str,
    result: _ReadResult,
    report: BudgetReport,
) -> round_parser.MarkdownArtifact | None:
    """Strictly parse a required fenced YAML mapping without raising."""
    if result.state == "missing":
        report.violations.append(
            SemanticViolation(filename, "MISSING_ARTIFACT", "required v16 artifact is missing")
        )
        return None
    if result.text is None:
        return None

    try:
        return round_parser.parse_frontmatter(result.text, filename=filename)
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation(filename, exc.kind, exc.message))
        return None


def _goal_entries(
    body: str,
    report: BudgetReport,
) -> list[tuple[str, str]] | None:
    """Extract exact ordered goal ids/titles and validate their links."""
    lines = body.splitlines()
    try:
        start = lines.index("## Goals") + 1
    except ValueError:
        report.violations.append(
            SemanticViolation("goal.md", "GOAL_ALIGNMENT", "body is missing '## Goals'")
        )
        return None

    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            section.append(line)

    entries: list[tuple[str, str]] = []
    for line in section:
        match = _GOAL_ENTRY_RE.fullmatch(line)
        if match is None or match.group(1) != match.group(3):
            report.violations.append(
                SemanticViolation(
                    "goal.md",
                    "GOAL_ALIGNMENT",
                    "goal entries must use '- Gn: title → checklist.md ## Gn' with equal ids",
                )
            )
            return None
        entries.append((match.group(1), match.group(2)))

    expected_ids = [f"G{index}" for index in range(1, len(entries) + 1)]
    if not entries or [entry[0] for entry in entries] != expected_ids:
        report.violations.append(
            SemanticViolation(
                "goal.md",
                "GOAL_ALIGNMENT",
                "goal ids must be contiguous and ordered from G1",
            )
        )
        return None
    return entries


def _checklist_goal_headings(
    body: str,
    report: BudgetReport,
) -> list[tuple[str, str]] | None:
    """Extract exact ordered ``## Gn: title`` checklist headings."""
    headings: list[tuple[str, str]] = []
    for line in body.splitlines():
        if not line.startswith("## G"):
            continue
        match = _CHECKLIST_GOAL_RE.fullmatch(line)
        if match is None:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "GOAL_ALIGNMENT",
                    "goal headings must use exact '## Gn: title' syntax",
                )
            )
            return None
        headings.append((match.group(1), match.group(2)))
    return headings


def _checklist_items(
    body: str,
    report: BudgetReport,
) -> list[round_parser.ChecklistItem] | None:
    """Adapt the shared item parser to deterministic lint findings."""
    try:
        items = round_parser._parse_checklist_items(  # noqa: SLF001
            body,
            "checklist.md",
            strict_metadata=False,
        )
    except round_parser.RoundArtifactParseError as exc:
        report.violations.append(SemanticViolation("checklist.md", exc.kind, exc.message))
        return None
    return list(items)


def _strict_frontmatter_equal(actual: object, expected: object) -> bool:
    """Compare derived frontmatter values without bool/int coercion."""
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            return False
        return all(_strict_frontmatter_equal(actual[key], value) for key, value in expected.items())
    return type(actual) is type(expected) and actual == expected


def _check_derived_field(
    filename: str,
    frontmatter: dict[str, object],
    field_name: str,
    expected: object,
    report: BudgetReport,
) -> None:
    """Compare one stored derived field with its body-derived value."""
    actual = frontmatter.get(field_name)
    if _strict_frontmatter_equal(actual, expected):
        return
    report.violations.append(
        SemanticViolation(
            filename,
            "DERIVED_FIELD",
            f"{field_name}={actual!r}; derived value is {expected!r}",
        )
    )


def _check_evidence_paths(
    change_folder: Path,
    items: list[round_parser.ChecklistItem],
    report: BudgetReport,
) -> None:
    """Require one exact, safe, regular evidence file per checked item."""
    for item in items:
        if not item.checked:
            continue
        evidence_lines = [line for line in item.metadata if line.lstrip().startswith("evidence:")]
        if len(evidence_lines) != 1:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} must declare exactly one evidence path",
                )
            )
            continue
        match = _EVIDENCE_METADATA_RE.fullmatch(evidence_lines[0])
        if match is None:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence metadata is malformed",
                )
            )
            continue
        declared = match.group(1)
        expected = f"evidence/{item.item_id}.txt"
        if declared != expected:
            report.violations.append(
                SemanticViolation(
                    "checklist.md",
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence path must be exactly {expected!r}",
                )
            )
            continue
        target = change_folder / expected
        try:
            regular_file = not target.is_symlink() and target.is_file()
        except OSError:
            regular_file = False
        if not regular_file:
            report.violations.append(
                SemanticViolation(
                    expected,
                    "EVIDENCE_PATH",
                    f"{item.item_id} evidence path is not an existing regular file",
                )
            )


def _check_progress_header(
    body: str,
    items: list[round_parser.ChecklistItem],
    stage_text: str | None,
    report: BudgetReport,
) -> None:
    """Require one pinned, byte-aligned effort-weighted ``## Progress`` header."""
    for item in items:
        for line in item.metadata:
            if (
                line.lstrip().startswith("effort:")
                and round_parser._EFFORT_RE.fullmatch(line) is None  # noqa: SLF001
            ):
                report.violations.append(
                    SemanticViolation(
                        "checklist.md",
                        "PROGRESS_HEADER",
                        f"{item.item_id} effort metadata must be an integer between 1 and 8",
                    )
                )

    lines = body.splitlines()
    heading_indices = [
        index for index, line in enumerate(lines) if line == progress_header.PROGRESS_HEADING
    ]
    if not heading_indices:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "checklist.md must pin a '## Progress' section directly after '# Checklist'",
            )
        )
        return
    if len(heading_indices) > 1:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "checklist.md must contain exactly one '## Progress' heading",
            )
        )
        return
    first_goal = next(
        (index for index, line in enumerate(lines) if line.startswith("## G")),
        None,
    )
    if first_goal is not None and heading_indices[0] > first_goal:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                "the '## Progress' section must precede the first goal partition",
            )
        )

    expected = progress_header.render_progress_line(
        progress_header.compute_progress_header(
            items,
            progress_header._lenient_stage(stage_text),  # noqa: SLF001
        )
    )
    actual = progress_header.extract_progress_line(body)
    if actual != expected:
        report.violations.append(
            SemanticViolation(
                "checklist.md",
                "PROGRESS_HEADER",
                f"progress line is stale or malformed; the derived line is {expected!r}",
            )
        )


__all__ = [
    name
    for name in globals()
    if name not in {"__name__", "__package__", "__loader__", "__spec__", "__builtins__", "__all__"}
]
