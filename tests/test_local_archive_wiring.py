from pathlib import Path

import yaml

from devolaflow.template_engine import TemplateRegistry
from devolaflow.template_engine.seeds import load_seed_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_ROOT = REPO_ROOT / "workflow-system" / "agent" / "templates"
REGISTRY_PATH = TEMPLATES_ROOT / "registry.yaml"
SEED_PATH = TEMPLATES_ROOT / "seeds" / "local-archive.yaml"

EXPECTED_PARTITIONS = [
    "inventory",
    "classify",
    "report-only-plan",
    "human-approval",
    "strict-clean-gate",
    "approved-move",
    "mapping-index-verification",
]
FORBIDDEN_EXECUTABLE_KEYS = {
    "stages",
    "composition",
    "loops",
    "gates",
    "team",
    "duration_class",
    "input_mapping",
    "skip_condition",
}


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _nested_keys(child)}
    return set()


def test_local_archive_seed_loads_from_registry() -> None:
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("local-archive")

    assert seed is not None
    assert seed.metadata.name == "local-archive"
    assert seed.metadata.category == "control"
    assert seed.metadata.source.kind == "composition"
    assert seed.metadata.source.name == "local-archive"
    assert seed.metadata.source.path == "workflow-system/agent/templates/registry.yaml"
    assert seed.source_stage_sequence() == [
        ("inventory", "analyze"),
        ("classify", "analyze"),
        ("plan", "plan"),
        ("approval", "review"),
        ("clean-gate", "gate"),
        ("move", "implement"),
        ("mapping-index", "verify"),
    ]
    raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry = load_seed_registry(REGISTRY_PATH)
    entry = registry["local-archive"]

    assert any(item["name"] == "local-archive" for item in raw["compositions"])
    assert all(item["name"] != "local-archive" for item in raw["templates"])
    assert entry.name == "local-archive"
    assert entry.seed == "seeds/local-archive.yaml"
    assert entry.category == "control"
    assert entry.path is None
    assert SEED_PATH.is_file()


def test_local_archive_seed_declares_bounded_archive_contract() -> None:
    raw = yaml.safe_load(SEED_PATH.read_text(encoding="utf-8"))
    statements = " ".join(
        assertion["statement_template"]
        for partition in raw["partitions"]
        for assertion in partition["assertions"]
    ).lower()

    assert [partition["key"] for partition in raw["partitions"]] == EXPECTED_PARTITIONS
    assert not FORBIDDEN_EXECUTABLE_KEYS & _nested_keys(raw)
    for phrase in (
        "without modification",
        "scan_workspace",
        "report-only",
        "explicitly approves",
        "strict",
        "no deletion",
        "append",
        "index",
    ):
        assert phrase in statements
    raw_text = SEED_PATH.read_text(encoding="utf-8")
    seed = TemplateRegistry(TEMPLATES_ROOT).load_seed("local-archive")

    assert "entropy-cleanup" not in raw_text
    assert seed is not None
    assert seed.metadata.source.name == "local-archive"
