"""CI guard for reference API alignment (schema-vs-doc + dataclass-vs-doc).

Per ``.local/research/v9.0.0_reference_review.md`` F-05 + F-06 (BLOCKER):
reference markdown carries dataclass + YAML code blocks that purport to
document live runtime APIs. Drift in either direction (doc shows fields
the code lacks, or doc omits required fields the code declares) crashes
on copy-paste and breaks operator trust.

This test parses code blocks from designated reference files and asserts
their declared field names match the canonical source-of-truth:

* ``references/memory-router.md`` §4 ``MemoryCase`` dataclass listing →
  matches ``src/devolaflow/memory_router/cache.py`` ``MemoryCase`` field
  set verbatim (closes F-05).
* ``references/message-schemas.md`` §7 cross-reference to
  ``layout_invariant.canonical_order`` length 16 → matches the live schema.

Long-term solution to the schema-vs-doc fabrication class. The PV-01
must-fix bundle (F-01 / F-05 / F-06 / F-14) closed the immediate
violations; this test prevents regression by failing CI on any future
drift.

Closes F-05 + F-06 long-term per
``.local/research/v9.0.0_implementation_plan.md`` §6.2.
"""

from __future__ import annotations

import re
from dataclasses import fields
from pathlib import Path

import pytest
import yaml

from devolaflow.memory_router.cache import MemoryCase

REPO_ROOT = Path(__file__).parent.parent
REFERENCES_DIR = REPO_ROOT / "workflow-system/agent/references"
SCHEMAS_DIR = REPO_ROOT / "schemas"

# ---------------------------------------------------------------------------
# Helpers — extract code blocks from markdown by section anchor
# ---------------------------------------------------------------------------

_FENCED_BLOCK_RE = re.compile(
    r"```(?P<lang>\w+)\n(?P<body>.*?)```",
    re.DOTALL | re.MULTILINE,
)


def _section_text(markdown: str, heading: str) -> str:
    """Return the body of a markdown section identified by ``heading``.

    The body runs from the heading line to the next heading at the same
    or higher level (or end-of-file). Heading match is exact (excluding
    leading ``#`` characters). The "next heading" regex requires the
    line to consist of ``#``s + space + a non-``#`` non-space character,
    which excludes YAML comment lines inside fenced code blocks (those
    typically have content text after ``# ``, but heading lines have
    only a heading title without extra ``#`` continuation — however a
    single ``# foo`` YAML comment WOULD match the H1 pattern by
    coincidence).

    To handle this safely, we additionally require the candidate
    heading line to NOT be inside a fenced code block (we strip code
    blocks from the rest before searching for the next heading).
    """
    pattern = re.compile(
        rf"^(#{{1,6}})\s+{re.escape(heading)}\s*$",
        re.MULTILINE,
    )
    match = pattern.search(markdown)
    if match is None:
        raise LookupError(f"section {heading!r} not found in markdown")
    start_level = len(match.group(1))
    start_pos = match.end()
    rest = markdown[start_pos:]
    # Mask fenced code-block bodies so YAML/Python comments starting
    # with `#` inside ```...``` don't get mistaken for headings.
    masked = re.sub(
        r"```.*?```",
        lambda m: "X" * len(m.group(0)),
        rest,
        flags=re.DOTALL,
    )
    next_heading = re.compile(
        rf"^#{{1,{start_level}}}\s+\S",
        re.MULTILINE,
    )
    next_match = next_heading.search(masked)
    if next_match is None:
        return rest
    return rest[: next_match.start()]


def _fenced_blocks(text: str, lang: str) -> list[str]:
    """Return the bodies of all fenced code blocks tagged ``lang``."""
    return [m.group("body") for m in _FENCED_BLOCK_RE.finditer(text) if m.group("lang") == lang]


_FIELD_LINE_RE = re.compile(
    r"^\s*(?P<name>[a-z_][a-zA-Z0-9_]*)\s*:\s*(?P<type>[^=#]+?)(?:\s*=\s*[^#]+)?(?:\s*#.*)?$"
)


def _python_dataclass_field_names(body: str) -> list[str]:
    """Parse field names from a Python ``@dataclass`` code block body.

    Skips the decorator + class line; emits every line that matches
    ``name: type`` or ``name: type = default``. Lines starting with
    ``#`` (comments) and blank lines are skipped.
    """
    names: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("@") or stripped.startswith("class "):
            continue
        match = _FIELD_LINE_RE.match(line)
        if match is None:
            continue
        names.append(match.group("name"))
    return names


# ---------------------------------------------------------------------------
# F-05 closure long-term — MemoryCase dataclass alignment
# ---------------------------------------------------------------------------


class TestMemoryCaseDocAlignment:
    """``references/memory-router.md`` §4 dataclass listing MUST match
    ``src/devolaflow/memory_router/cache.py::MemoryCase`` exactly.

    F-05 (BLOCKER): the doc previously listed fabricated fields
    (``dispatch_template``, ``expected_savings_pp``) and omitted
    required ``summary``. PV-01 fixed the body; this test prevents
    regression.
    """

    MEMORY_ROUTER_PATH = REFERENCES_DIR / "memory-router.md"

    def test_memory_router_md_exists(self) -> None:
        assert self.MEMORY_ROUTER_PATH.exists(), (
            f"missing memory-router.md at {self.MEMORY_ROUTER_PATH} — "
            "this reference is the canonical entry for memory-router APIs"
        )

    def test_memory_case_field_set_matches_source(self) -> None:
        """The §5.3 dataclass listing field names MUST equal the
        :class:`MemoryCase` field set verbatim (no fabrications, no
        omissions). Closes F-05."""
        markdown = self.MEMORY_ROUTER_PATH.read_text(encoding="utf-8")
        section = _section_text(markdown, "4. `MemoryCase` Value Type")
        py_blocks = _fenced_blocks(section, "python")
        assert py_blocks, (
            "no python code block in §5.3 — F-05 fix omitted the MemoryCase dataclass listing"
        )
        # The first python block is the canonical dataclass listing.
        doc_field_names = set(_python_dataclass_field_names(py_blocks[0]))
        source_field_names = {f.name for f in fields(MemoryCase)}
        fabricated = doc_field_names - source_field_names
        assert not fabricated, (
            f"memory-router.md §4 lists fabricated MemoryCase fields {sorted(fabricated)} "
            f"that don't exist in src/devolaflow/memory_router/cache.py — F-05 regressed"
        )
        from dataclasses import MISSING

        canonical_required = {
            f.name
            for f in fields(MemoryCase)
            if f.default is MISSING and f.default_factory is MISSING
        }
        missing_in_doc = canonical_required - doc_field_names
        assert not missing_in_doc, (
            f"memory-router.md §4 omits required MemoryCase fields {sorted(missing_in_doc)} — "
            f"F-05 regressed; required fields are: {sorted(canonical_required)}"
        )

    def test_memory_case_summary_field_documented(self) -> None:
        """Specific F-05 regression guard: ``summary`` field MUST appear
        in the §5.3 dataclass listing (the original F-05 omission)."""
        markdown = self.MEMORY_ROUTER_PATH.read_text(encoding="utf-8")
        section = _section_text(markdown, "4. `MemoryCase` Value Type")
        py_blocks = _fenced_blocks(section, "python")
        doc_fields = set(_python_dataclass_field_names(py_blocks[0]))
        assert "summary" in doc_fields, (
            "memory-router.md §4 omits the canonical `summary` field — "
            "F-05 has regressed. Re-add per src/devolaflow/memory_router/cache.py:91-136."
        )

    def test_memory_case_no_fabricated_dispatch_template(self) -> None:
        """Specific F-05 regression guard: ``dispatch_template`` field
        was fabricated in the original F-05 violation. It MUST NOT
        reappear in §5.3."""
        markdown = self.MEMORY_ROUTER_PATH.read_text(encoding="utf-8")
        section = _section_text(markdown, "4. `MemoryCase` Value Type")
        py_blocks = _fenced_blocks(section, "python")
        doc_fields = set(_python_dataclass_field_names(py_blocks[0]))
        assert "dispatch_template" not in doc_fields, (
            "memory-router.md §4 contains the fabricated `dispatch_template` field — "
            "F-05 has regressed. This field does NOT exist in MemoryCase."
        )
        assert "expected_savings_pp" not in doc_fields, (
            "memory-router.md §4 contains the fabricated `expected_savings_pp` field — "
            "F-05 has regressed. This field does NOT exist in MemoryCase."
        )


# ---------------------------------------------------------------------------
# F-02 closure long-term — context-isolation.md 16-keys verbatim
# ---------------------------------------------------------------------------


class TestContextIsolationCanonicalKeys:
    """``references/context-isolation.md`` §10 MUST cite the live
    ``layout_invariant.canonical_order`` length (currently 16). F-02
    (BLOCKER): the doc previously declared "12 keys" — 4 schema
    generations stale. PV-02 closed this; this test prevents regression.
    """

    CONTEXT_ISOLATION_PATH = REFERENCES_DIR / "context-isolation.md"
    LEAN_DISPATCH_SCHEMA = SCHEMAS_DIR / "lean-dispatch.yaml"

    def test_documents_live_canonical_order_length(self) -> None:
        """The §10 'Canonical order (N keys, ...)' phrase MUST cite the
        live ``layout_invariant.canonical_order`` length."""
        markdown = self.CONTEXT_ISOLATION_PATH.read_text(encoding="utf-8")
        schema = yaml.safe_load(self.LEAN_DISPATCH_SCHEMA.read_text(encoding="utf-8"))
        live_length = len(schema["layout_invariant"]["canonical_order"])
        live_version = schema["layout_invariant"]["version"]
        # Match patterns like "Canonical order (16 keys, `version: 5`)".
        pattern = re.compile(
            rf"Canonical order \({live_length} keys,\s*`version:\s*{live_version}`",
            re.IGNORECASE,
        )
        assert pattern.search(markdown), (
            f"context-isolation.md §10 does NOT declare 'Canonical order ({live_length} keys, "
            f"`version: {live_version}`)' — F-02 has regressed. Update §10 to cite the live "
            f"schemas/lean-dispatch.yaml#layout_invariant length ({live_length}) and "
            f"version ({live_version})."
        )

    def test_does_not_cite_stale_canonical_order_length(self) -> None:
        """The §10 paragraph MUST NOT carry a stale 'Canonical order (N keys, ...)'
        phrase for any N != live length. F-02 regression guard."""
        markdown = self.CONTEXT_ISOLATION_PATH.read_text(encoding="utf-8")
        schema = yaml.safe_load(self.LEAN_DISPATCH_SCHEMA.read_text(encoding="utf-8"))
        live_length = len(schema["layout_invariant"]["canonical_order"])
        # Find every "Canonical order (N keys" occurrence and assert N == live.
        for match in re.finditer(r"Canonical order \((\d+) keys", markdown):
            cited = int(match.group(1))
            assert cited == live_length, (
                f"context-isolation.md cites 'Canonical order ({cited} keys' but live "
                f"layout_invariant.canonical_order is length {live_length}. F-02 regressed."
            )


# ---------------------------------------------------------------------------
# F-03 closure long-term — message-schemas.md lean format mandate
# ---------------------------------------------------------------------------


class TestMessageSchemasLeanFormat:
    """``references/message-schemas.md`` MUST cite C-2 lean-form mandate.
    F-03 (BLOCKER): the doc previously documented only the verbose
    legacy schema. PV-02 closed this; this test prevents regression.
    """

    MESSAGE_SCHEMAS_PATH = REFERENCES_DIR / "message-schemas.md"

    def test_cites_lean_form_canonical_mandate(self) -> None:
        markdown = self.MESSAGE_SCHEMAS_PATH.read_text(encoding="utf-8")
        # The doc MUST mention "lean format" + the C-2 rule.
        assert re.search(r"\blean\s+format\b", markdown, re.IGNORECASE), (
            "message-schemas.md does NOT mention 'lean format' — F-03 has regressed. "
            "The lean form is the canonical authoring shape per CO-1 / C-2; "
            "verbose form is the deprecated R5 appendix."
        )

    def test_layout_invariant_section_present(self) -> None:
        """§7 'Layout Invariant' section MUST exist (added in PV-02)."""
        markdown = self.MESSAGE_SCHEMAS_PATH.read_text(encoding="utf-8")
        assert re.search(r"^##\s+7\.\s+Layout Invariant", markdown, re.MULTILINE), (
            "message-schemas.md missing §7 'Layout Invariant' section — F-03 partial regression"
        )


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_all_canonical_references_load() -> None:
    """Every reference file referenced by the alignment tests above MUST exist."""
    for path in [
        REFERENCES_DIR / "memory-router.md",
        REFERENCES_DIR / "context-isolation.md",
        REFERENCES_DIR / "message-schemas.md",
    ]:
        assert path.is_file(), f"missing canonical reference: {path}"


@pytest.mark.parametrize(
    "schema_path",
    [
        SCHEMAS_DIR / "lean-dispatch.yaml",
    ],
    ids=lambda p: p.name,
)
def test_referenced_schemas_load(schema_path: Path) -> None:
    """Every schema cross-referenced by the alignment tests MUST parse."""
    assert schema_path.is_file(), f"missing schema: {schema_path}"
    data = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{schema_path} does not parse as a YAML mapping"
