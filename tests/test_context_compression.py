"""Selector-backed L1/L2 context compression contracts."""

from __future__ import annotations

from pathlib import Path

from devolaflow.compressor import apply_context_assembly, assemble_context


def _selector_output() -> dict:
    return {
        "profile_name": "hotfix",
        "compression_intensity": "standard",
        "assembled_text": "Basically, please fix this. I think the fix is small.",
    }


def test_assembly_uses_actual_agents_slice_and_measures_reduction(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Soul Rules\n\n## S-1 — Keep dispatchers thin\n\n"
        "# Workflow Rules\n\n## W-1 — Research first\n\n"
        "## W-9 — Run tests\n",
        encoding="utf-8",
    )
    assembly = assemble_context(
        _selector_output(),
        task_type="hotfix",
        layer="L2",
        agents_md_path=agents,
    )

    assert "## W-1" not in assembly["rule_text"]
    assert "## W-9" in assembly["rule_text"]
    assert assembly["source"] == "selector"
    assert assembly["profile"] == "hotfix"
    assert assembly["layer"] == "L2"
    assert assembly["measurement"]["status"] == "AVAILABLE"
    assert assembly["measurement"]["token_reduction"] >= 0
    assert assembly["measurement"]["rule"]["status"] == "AVAILABLE"


def test_standard_compression_removes_narration_but_preserves_rules() -> None:
    assembly = assemble_context(
        {
            "profile_name": "feature",
            "compression_intensity": "standard",
            "assembled_text": "Basically, please implement src/auth.py. I think it works.",
            "agents_md_text": "src/auth.py\nError: preserve this exact value",
        },
        task_type="feature",
        layer="L2",
    )

    assert assembly["intensity"] == "standard"
    assert "Basically" not in assembly["skill_text"]
    assert "src/auth.py" in assembly["skill_text"]
    assert "Error: preserve this exact value" in assembly["rule_text"]


def test_safety_and_destructive_contexts_bypass_verbatim() -> None:
    source = "WARNING: do not compress this; rm -rf build/"
    assembly = assemble_context(
        {
            "profile_name": "feature",
            "assembled_text": source,
            "agents_md_text": "rule text",
        },
        task_type="feature",
        layer="L2",
    )

    assert assembly["skill_text"] == source
    assert assembly["preserve_list_bypass"] is True
    assert {"security_warning", "destructive_operation"} <= set(assembly["bypass_reasons"])
    assert assembly["measurement"]["token_reduction"] == 0


def test_audit_profile_bypasses_and_missing_measurement_is_explicit() -> None:
    audit = assemble_context(
        {
            "profile_name": "security-audit",
            "assembled_text": "Please preserve the audit evidence.",
            "agents_md_text": "commit abcdef1234567",
        },
        task_type="security-audit",
        layer="L1",
    )
    missing = assemble_context({}, task_type="", layer="L2")

    assert audit["preserve_list_bypass"] is True
    assert "audit_context" in audit["bypass_reasons"]
    assert audit["skill_text"] == "Please preserve the audit evidence."
    assert missing["measurement"]["status"] == "INSUFFICIENT"
    assert missing["measurement"]["tokens_in"] is None
    assert missing["measurement"]["token_reduction"] is None


def test_apply_assembly_nests_under_rules_without_mutating_or_reordering() -> None:
    dispatch = {
        "hdr": {"id": "d1"},
        "task": {"id": "T1"},
        "files": ["src/auth.py"],
        "rules": {"strategy": "standard"},
        "shared": "python",
        "gate": {"retries": 2},
    }
    assembly = assemble_context(
        {
            "profile_name": "feature",
            "assembled_text": "please update src/auth.py",
            "agents_md_text": "rules",
        },
        task_type="feature",
    )
    result = apply_context_assembly(dispatch, assembly)

    assert list(result) == list(dispatch)
    assert result["rules"]["text"] == "rules"
    assert result["rules"]["compression"]["profile"] == "feature"
    assert "text" not in dispatch["rules"]
