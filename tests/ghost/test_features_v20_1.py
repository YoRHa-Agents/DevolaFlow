"""Current-cycle W-18 ghost audit for the v20.1 Retro-Digest contract."""

from __future__ import annotations

import inspect
import tomllib
from pathlib import Path

import pytest
import yaml

from tests.ghost.test_registries import _SF4_REFERENCE_SET

_EXPECTED_EXPORTS = {
    "DigestCategory",
    "DigestCuration",
    "DigestRecord",
    "DigestResult",
    "DigestStatus",
    "DigestVerdict",
    "RetroDigestVerdict",
    "RetrospectiveSource",
    "build_digest",
    "capture_digest_entries",
    "classify_retro_digest_intent",
    "discover_evaluations",
    "discover_retrospectives",
    "extract_digest_records",
    "extract_evaluation_findings",
    "extract_retrospective_records",
    "render_digest_report",
    "to_learning_entries",
}


def test_v20_1_retro_digest_runtime_exports_and_intent_contract() -> None:
    """The runtime is importable, exported, and natural-language only."""
    import devolaflow.skills as skills
    import devolaflow.skills.retro_digest as runtime

    assert set(runtime.__all__) == _EXPECTED_EXPORTS
    assert set(skills.__all__) >= _EXPECTED_EXPORTS
    assert Path(runtime.__file__).name == "retro_digest.py"
    assert runtime.classify_retro_digest_intent("Please create a retro digest") == (
        "DIGEST_REQUESTED"
    )
    assert runtime.classify_retro_digest_intent("What did we learn this cycle?") == (
        "DIGEST_SUGGESTED"
    )
    assert runtime.classify_retro_digest_intent("Implement the endpoint") == "NO_DIGEST"
    assert runtime.classify_retro_digest_intent("") == "NO_DIGEST"


@pytest.mark.parametrize(
    ("heading", "lesson"),
    [
        ("## Key learnings", "Preserve this exact English lesson: 91.0%"),
        ("## 关键学习", "保留这条精确的中文学习：91.0%"),
    ],
)
def test_v20_1_bilingual_extraction_preserves_relative_provenance(
    heading: str, lesson: str
) -> None:
    """English and Chinese learning sections retain exact source evidence."""
    from devolaflow.skills import extract_retrospective_records

    source_path = ".local/research/v20.1.0_retrospective.md"
    records = extract_retrospective_records(
        f"# Retrospective\n\n{heading}\n- {lesson}\n\n## Next\n- ignored",
        source_path=source_path,
    )

    assert len(records) == 1
    record = records[0]
    assert record.text == lesson
    assert record.raw_text == f"- {lesson}"
    assert record.source_path == source_path
    assert record.source_span == (3, 3)
    assert record.source_kind == "retrospective"
    assert record.record_id == f"{source_path}#L3"


def test_v20_1_evaluation_findings_are_verbatim_benefits() -> None:
    """Evaluation findings preserve numeric/table evidence as report-only benefits."""
    from devolaflow.skills import extract_evaluation_findings

    source_path = "docs/cycle-archive/v20.0.0/evaluation/v20.0.0_evaluation.md"
    records = extract_evaluation_findings(
        """# Evaluation

### Findings Closure
- W-17 observation is `51`
| score | value |
|---|---:|
| test adequacy | 6.67 |

## Other section
- ignored
""",
        source_path=source_path,
    )

    assert [record.text for record in records] == [
        "W-17 observation is `51`",
        "| score | value |",
        "| test adequacy | 6.67 |",
    ]
    assert all(record.category == "benefit" for record in records)
    assert all(record.source_kind == "evaluation" for record in records)
    assert all(not record.source_path.startswith("/") for record in records)


def test_v20_1_digest_ordering_and_duplicate_precedence_are_deterministic(
    tmp_path: Path,
) -> None:
    """Current research wins duplicate archives and repeated reports are identical."""
    from devolaflow.skills import build_digest, discover_retrospectives, render_digest_report

    current = tmp_path / ".local" / "research"
    archived = tmp_path / "docs" / "cycle-archive" / "v2.0.0"
    current.mkdir(parents=True)
    archived.mkdir(parents=True)
    (current / "v2.0.0_retrospective.md").write_text(
        "## Key learnings\n- current exact lesson\n",
        encoding="utf-8",
    )
    (archived / "v2.0.0_retrospective.md").write_text(
        "## Key learnings\n- archived duplicate must lose\n",
        encoding="utf-8",
    )
    (archived / "v1.0.0_retrospective.md").write_text(
        "## Key learnings\n- older exact lesson\n",
        encoding="utf-8",
    )

    sources = discover_retrospectives(tmp_path)
    assert [source.path for source in sources] == [
        ".local/research/v2.0.0_retrospective.md",
        "docs/cycle-archive/v2.0.0/v1.0.0_retrospective.md",
    ]
    digest = build_digest(tmp_path)
    first = render_digest_report(digest)
    second = render_digest_report(digest)
    assert first == second
    assert "current exact lesson" in first
    assert "archived duplicate must lose" not in first
    assert all(not record.source_path.startswith("/") for record in digest.records)


def test_v20_1_report_only_default_and_explicit_consent_boundary(tmp_path: Path) -> None:
    """Digest review is read-only until the explicit capture helper is invoked."""
    from devolaflow.skills import (
        DigestCuration,
        build_digest,
        capture_digest_entries,
        to_learning_entries,
    )

    research = tmp_path / ".local" / "research"
    research.mkdir(parents=True)
    (research / "v20.1.0_retrospective.md").write_text(
        "## Key learnings\n- Keep this source passage verbatim\n",
        encoding="utf-8",
    )
    evaluation = research / "v20.1.0_evaluation.md"
    evaluation.write_text(
        "## Evaluation Findings\n- Benefit stays report-only\n",
        encoding="utf-8",
    )
    operational = tmp_path / ".local" / "memory" / "operational.jsonl"
    digest = build_digest(tmp_path)

    assert digest.status == "OK"
    assert not operational.exists()
    assert "capture_digest_entries" not in inspect.getsource(build_digest)
    selected = DigestCuration.select([digest.lessons[0].record_id], labels=(("scope", "cycle"),))
    entries = to_learning_entries(digest, selected)
    assert len(entries) == 1
    assert entries[0].insight == "Keep this source passage verbatim"
    assert not any(entry.insight == "Benefit stays report-only" for entry in entries)
    assert capture_digest_entries(entries, operational) == (True,)
    assert operational.is_file()


def test_v20_1_seed_registry_has_four_bounded_partitions(project_root: Path) -> None:
    """The selectable seed is registered with exactly four declarative partitions."""
    from devolaflow.template_engine.registry import TemplateRegistry

    templates = project_root / "workflow-system" / "agent" / "templates"
    registry = yaml.safe_load((templates / "registry.yaml").read_text(encoding="utf-8"))
    entry = next(item for item in registry["compositions"] if item["name"] == "retro-digest")
    assert entry["seed"] == "seeds/retro-digest.yaml"
    seed_path = templates / entry["seed"]
    assert seed_path.is_file()
    seed = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    assert seed["metadata"]["name"] == "retro-digest"
    assert [partition["key"] for partition in seed["partitions"]] == [
        "grilling-decision-contract",
        "phase-0-read-only-audits",
        "bounded-pv-implementation",
        "cycle-close-and-digest",
    ]
    assert all(
        "stages" not in partition and "loops" not in partition for partition in seed["partitions"]
    )
    assert TemplateRegistry(templates).load_seed("retro-digest") is not None


def test_v20_1_reference_manifest_and_sf4_registration(project_root: Path) -> None:
    """The dedicated reference is installed and visible in every C-7 view."""
    reference = project_root / "workflow-system/agent/references/retro-digest.md"
    manifest = yaml.safe_load(
        (project_root / "workflow-system/agent/manifest.yaml").read_text(encoding="utf-8")
    )
    skill = (project_root / "workflow-system/agent/SKILL.md").read_text(encoding="utf-8")

    assert reference.is_file()
    assert "retro-digest.md" in _SF4_REFERENCE_SET
    assert "references/retro-digest.md" in manifest["references"]
    assert "references/retro-digest.md" in skill
    reference_text = reference.read_text(encoding="utf-8")
    assert "Verbatim evidence" in reference_text
    assert "report-only" in reference_text
    assert "explicit operator consent" in reference_text


def test_v20_1_w29_is_compiled_and_indexed(project_root: Path) -> None:
    """W-29 is source-authored, compiled, counted, and reference-indexed."""
    source = (project_root / ".rules/workflow.mdc").read_text(encoding="utf-8")
    index = (project_root / ".rules/index.md").read_text(encoding="utf-8")
    compiled = (
        (project_root / "AGENTS.md").read_text(encoding="utf-8"),
        (project_root / ".cursor/rules/repo-governance.mdc").read_text(encoding="utf-8"),
    )

    assert "## W-29 — Retro-Digest Evidence and Consent" in source
    assert "Total rules: **51**" in index
    assert "22 (W-1..W-9, W-16..W-18, W-20..W-29)" in index
    assert "| W-29 | `workflow-system/agent/references/retro-digest.md` |" in index
    assert all("## W-29 — Retro-Digest Evidence and Consent" in text for text in compiled)


def test_v20_1_adds_no_env_flag_or_cli_and_has_current_gap_evidence(
    project_root: Path,
) -> None:
    """The feature remains natural-language-only and has SI-1 evidence."""
    runtime = (project_root / "src/devolaflow/skills/retro_digest.py").read_text(encoding="utf-8")
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    script_names = set(pyproject["project"]["scripts"])
    gap = project_root / "docs/cycle-archive/v20.1.0/v20.1.0_gap_analysis.md"

    assert "DEVOLAFLOW_" not in runtime
    assert "argparse" not in runtime
    assert not any("retro" in name.casefold() for name in script_names)
    assert gap.is_file()
    gap_text = gap.read_text(encoding="utf-8")
    for evidence in (
        "# v20.1.0 Retro-Digest — SI-1 Gap Analysis",
        "The implementation must preserve these decisions",
        "Deterministic base extraction",
        "Verbatim source preservation",
        "Report-only by default",
        "No new environment flag or CLI is planned",
        "src/devolaflow/skills/retro_digest.py",
    ):
        assert evidence in gap_text
    assert "does not claim that the feature exists" in gap_text
