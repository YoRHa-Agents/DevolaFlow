"""Deterministic generation and bilingual guide contract tests."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from scripts import generate_human_docs


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.md")):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _timestamps(root: Path) -> set[str]:
    return {
        re.search(r'^last_synced: "([^"]+)"$', path.read_text(), re.MULTILINE).group(1)
        for path in root.rglob("*.md")
    }


def test_unchanged_semantics_preserve_timestamp_and_bytes(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "en"
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1704067200")
    changed = generate_human_docs._gen_doc(
        "quickstart",
        "Quick Start Guide",
        "Install and verify.",
        "en",
        output,
        humanize=False,
    )
    first = (output / "quickstart.md").read_bytes()

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    changed_again = generate_human_docs._gen_doc(
        "quickstart",
        "Quick Start Guide",
        "Install and verify.",
        "en",
        output,
        humanize=False,
    )

    assert changed is True
    assert changed_again is False
    assert (output / "quickstart.md").read_bytes() == first
    assert b'last_synced: "2024-01-01T00:00:00Z"' in first


def test_semantic_change_uses_source_date_epoch(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "en"
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1704067200")
    generate_human_docs._gen_doc("faq", "FAQ", "First description.", "en", output, humanize=False)

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1735689600")
    changed = generate_human_docs._gen_doc(
        "faq", "FAQ", "Changed description.", "en", output, humanize=False
    )
    text = (output / "faq.md").read_text(encoding="utf-8")

    assert changed is True
    assert 'last_synced: "2025-01-01T00:00:00Z"' in text
    assert "Changed description." in text


def test_full_run_uses_one_clock_and_is_byte_idempotent(tmp_path: Path) -> None:
    generated, changed = generate_human_docs.generate_docs(
        tmp_path,
        humanize=False,
        synced_at="2026-01-02T03:04:05Z",
    )
    first_hash = _tree_hash(tmp_path)

    generated_again, changed_again = generate_human_docs.generate_docs(
        tmp_path,
        humanize=False,
        synced_at="2027-02-03T04:05:06Z",
    )

    assert generated == generated_again == len(generate_human_docs.DOCS) * 2
    assert changed == generated
    assert changed_again == 0
    assert _tree_hash(tmp_path) == first_hash
    assert _timestamps(tmp_path) == {"2026-01-02T03:04:05Z"}


def test_zh_seed_description_keys_must_match_registry(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invalid = dict(generate_human_docs.ZH_SEED_DESCRIPTIONS)
    invalid.pop("hotfix")
    invalid["unexpected"] = "不应存在。"
    monkeypatch.setattr(generate_human_docs, "ZH_SEED_DESCRIPTIONS", invalid)

    with pytest.raises(ValueError, match="must match registry names exactly") as exc_info:
        generate_human_docs._load_inventory(project_root)

    message = str(exc_info.value)
    assert "hotfix" in message
    assert "unexpected" in message


def test_committed_guides_match_generator_and_keep_en_zh_parity(
    project_root: Path, tmp_path: Path
) -> None:
    generated_root = tmp_path / "human"
    generate_human_docs.generate_docs(
        generated_root,
        humanize=True,
        synced_at="2000-01-01T00:00:00Z",
    )
    committed_root = project_root / "workflow-system" / "human"

    for slug, *_ in generate_human_docs.DOCS:
        en = (committed_root / "en" / f"{slug}.md").read_text(encoding="utf-8")
        zh = (committed_root / "zh" / f"{slug}.md").read_text(encoding="utf-8")
        generated_en = (generated_root / "en" / f"{slug}.md").read_text(encoding="utf-8")
        generated_zh = (generated_root / "zh" / f"{slug}.md").read_text(encoding="utf-8")

        assert generate_human_docs._semantic_text(en) == generate_human_docs._semantic_text(
            generated_en
        )
        assert generate_human_docs._semantic_text(zh) == generate_human_docs._semantic_text(
            generated_zh
        )
        assert re.findall(r"^(#+) ", en, re.MULTILINE) == re.findall(r"^(#+) ", zh, re.MULTILINE)
        assert en.count("```") == zh.count("```")

    profiles = {name for name, _, _ in generate_human_docs.INVENTORY.profiles}
    en_integration = (committed_root / "en" / "integration-guide.md").read_text()
    zh_integration = (committed_root / "zh" / "integration-guide.md").read_text()
    assert all(f"`{profile}`" in en_integration for profile in profiles)
    assert all(f"`{profile}`" in zh_integration for profile in profiles)

    seed_order = [str(entry["name"]) for entry in generate_human_docs.INVENTORY.seeds]
    en_workflows = (committed_root / "en" / "workflow-types.md").read_text()
    zh_workflows = (committed_root / "zh" / "workflow-types.md").read_text()
    assert "| Seed ID | Category | Canonical description | Intent tags |" in en_workflows
    assert "| 种子 ID | 类别 | 本地化描述 | 意图标签 |" in zh_workflows
    assert re.findall(r"^\| `([^`]+)` \|", en_workflows, re.MULTILINE) == seed_order
    assert re.findall(r"^\| `([^`]+)` \|", zh_workflows, re.MULTILINE) == seed_order
    assert all(
        description in zh_workflows
        for description in generate_human_docs.ZH_SEED_DESCRIPTIONS.values()
    )

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for lang in ("en", "zh")
        for path in sorted((committed_root / lang).glob("*.md"))
    )
    assert "$INSTALLER" not in combined
    assert "devola-init doctor" not in combined
    assert "devola-init sync-rules" not in combined
