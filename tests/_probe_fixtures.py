"""Workspace builders for the v7.0.3 persistence probe (ADR-004).

This module is **test-only**. It synthesises the Stage A artifact, the
Stage B lean dispatch, and the Stage B context-packed YAML under a caller-
provided ``tmp_path`` so the probe harness can exercise the full
``summarise_predecessor`` → renderer → Stage B dispatch integration without
touching any production code path. The three probe scenarios (easy / medium
/ hard) match ADR-004 §2.2's entity-count tiers.

Kept next to ``tests/conftest.py`` rather than in ``src/`` because ADR-004
§3 classifies the entity-extraction and carry-through assertion as test
infrastructure (the production consumer is the dispatcher, not the probe).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from devolaflow.compressor import (
    DEFAULT_DISPATCH_LAYOUT,
    assert_dispatch_layout,
    extract_named_entities,
    summarise_predecessor,
)

SCENARIO_SPECS: dict[str, dict] = {
    "easy": {"entity_target": 5, "body_tokens": 500},
    "medium": {"entity_target": 20, "body_tokens": 5000},
    "hard": {"entity_target": 50, "body_tokens": 15000},
}


def _seed_entities(count: int) -> list[str]:
    """Return a list of ``count`` deterministic preserve-list strings.

    Cycles through file paths, task ids, version strings, commit hashes,
    metric values, and interface signatures so every scenario exercises a
    cross-section of ``extract_named_entities``'s eight entity classes.
    """
    templates = [
        "src/devolaflow/module_{i:03d}.py",
        "tests/test_module_{i:03d}.py",
        "T-E2E-{i:03d}",
        "S01-W{i:02d}",
        "version 7.0.{i}",
        "abcdef{i:07d}",
        "0.{i}2 s latency",
        "{i} ms budget",
        "def handle_{i:03d}(payload: dict) -> dict",
        "class Widget{i:03d}",
    ]
    seeds: list[str] = []
    for idx in range(count):
        tpl = templates[idx % len(templates)]
        try:
            seeds.append(tpl.format(i=idx))
        except (IndexError, KeyError):
            seeds.append(tpl)
    return seeds


def _build_preserve_panel(seeds: list[str]) -> str:
    """Return a markdown ``## Preserve-list`` section containing every seed.

    Emits one line per seed in the form ``- ``seed`` (type)`` so that
    ``extract_named_entities`` surfaces every seed at least once. Rendered
    under an H2 because the summariser's default priority keeps H2 headings.
    """
    lines = ["## Preserve-list (do not paraphrase)", ""]
    for seed in seeds:
        lines.append(f"- {seed}")
    lines.append("")
    return "\n".join(lines)


def _build_filler_body(tokens_target: int) -> str:
    """Return filler markdown sized to approximately ``tokens_target`` tokens.

    Uses the deterministic ``len(text) // 4`` fallback estimator contract:
    the conftest's ``_force_fallback_token_estimator`` only applies to the
    benchmarks file, so we intentionally generate enough characters to cover
    both the fallback and any tiktoken path by rounding up.
    """
    if tokens_target <= 0:
        return ""
    approx_chars = max(400, tokens_target * 4)
    paragraph = (
        "## Context Body\n\n"
        "This section fills the artifact to an approximate token target so "
        "the summariser has to decide which sections to keep under the "
        "hard-capped token budget. It contains no entities that should "
        "survive the Stage-A to Stage-B boundary on its own; the preserve-"
        "list panel above is the ground truth.\n\n"
    )
    sentence = (
        "Dispatchers running under the ADR-003 extractive mode must emit a "
        "`key_facts:` prefix before any narrative body, and per ADR-004 the "
        "persistence probe asserts entity carry-through against the panel. "
    )
    body_chunks: list[str] = [paragraph]
    while sum(len(chunk) for chunk in body_chunks) < approx_chars:
        body_chunks.append(sentence)
    return "".join(body_chunks)


def _write_artifact(
    stage_a_dir: Path,
    scenario: str,
    *,
    paraphrase_file_path: bool = False,
) -> tuple[Path, list[str]]:
    """Write the Stage A artifact and return ``(path, seeds)``."""
    spec = SCENARIO_SPECS[scenario]
    seeds = _seed_entities(spec["entity_target"])
    if paraphrase_file_path and seeds:
        # Replace the first file-path-like seed with a paraphrase so the
        # probe's FAIL path fires deterministically.
        for idx, seed in enumerate(seeds):
            if seed.endswith(".py"):
                seeds[idx] = "the compressor module"
                break
    panel = _build_preserve_panel(seeds)
    body = _build_filler_body(spec["body_tokens"])
    artifact_text = (
        "# Stage A — Research Artifact (probe scenario: " + scenario + ")\n\n" + panel + "\n" + body
    )
    artifact_path = stage_a_dir / "artifact.md"
    stage_a_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(artifact_text, encoding="utf-8")
    return artifact_path, seeds


def _canonical_dispatch(summary_text: str, scenario: str) -> dict:
    """Build a minimal canonical-layout dispatch payload for Stage B.

    Embeds ``summary_text`` verbatim inside ``pred[0].key_facts`` so the
    carry-through check exercises the real integration point (summariser
    output → Stage B dispatch) rather than a helper abstraction.
    """
    payload: dict = {
        "hdr": {
            "id": f"d-probe-{scenario}",
            "parent": "stage-a",
            "layer": "wave",
        },
        "task": {
            "id": "T-PROBE-001",
            "type": "impl",
            "title": f"persistence probe {scenario}",
        },
        "goal": "verify Stage A entities survive to Stage B dispatch",
        "assumptions": ["summariser is extractive and verbatim"],
        "pred": [
            {
                "ref": "stage_a/artifact.md",
                "summary_mode": "extractive",
                "summary_max_tokens": 1200,
                "key_facts": summary_text,
            }
        ],
        "files": ["stage_b/dispatch.yaml", "stage_b/context_packed.yaml"],
        "rules": {"strategy": "standard", "lang": "python"},
        "shared": "Python 3.11+, ruff, pytest",
        "accept": ["probe entity carry-through >= scenario threshold"],
        "verify_cfg": {"visual": False, "accept": True},
        "gate": {"coverage": 90, "quality": 85, "blockers": 0, "retries": 2},
    }
    return payload


def build_probe_workspace(
    tmp_path: Path,
    scenario: str = "easy",
    *,
    paraphrase_file_path: bool = False,
    summary_max_tokens: int = 1200,
    retrieval_query: str | None = None,
) -> dict:
    """Return a dict describing a freshly-built Stage A + Stage B workspace.

    ``retrieval_query`` (added in v7.2.5 P-05) is forwarded verbatim to
    :func:`devolaflow.compressor.summarise_predecessor`. When omitted/None
    behaviour is byte-identical to v7.2.4 and earlier (the existing 3-tier
    easy/medium/hard persistence probe in ``tests/test_e2e_compression.py``
    relies on this default-preservation guarantee).
    """
    if scenario not in SCENARIO_SPECS:
        raise ValueError(f"unknown scenario {scenario!r}; expected one of {list(SCENARIO_SPECS)}")

    stage_a_dir = tmp_path / "stage_a"
    stage_b_dir = tmp_path / "stage_b"
    stage_b_dir.mkdir(parents=True, exist_ok=True)

    artifact_path, seeds = _write_artifact(
        stage_a_dir, scenario, paraphrase_file_path=paraphrase_file_path
    )

    summary = summarise_predecessor(
        artifact_path=str(artifact_path),
        max_tokens=summary_max_tokens,
        mode="extractive",
        retrieval_query=retrieval_query,
    )
    dispatch_payload = _canonical_dispatch(summary["summary_text"], scenario)
    assert_dispatch_layout(dispatch_payload, layout_spec=DEFAULT_DISPATCH_LAYOUT)

    dispatch_path = stage_b_dir / "dispatch.yaml"
    dispatch_path.write_text(
        yaml.safe_dump(dispatch_payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    context_packed_payload = {
        "scenario": scenario,
        "stage_a_artifact": str(artifact_path),
        "summary_token_count": summary["token_count"],
        "summary_was_bounded": summary["was_bounded"],
        "covered_sections": summary["covered_sections"],
        "dropped_sections": summary["dropped_sections"],
    }
    context_packed_path = stage_b_dir / "context_packed.yaml"
    context_packed_path.write_text(
        yaml.safe_dump(context_packed_payload, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    artifact_entities = extract_named_entities(artifact_path.read_text(encoding="utf-8"))

    return {
        "scenario": scenario,
        "stage_a_artifact": artifact_path,
        "stage_b_dispatch": dispatch_path,
        "stage_b_context_packed": context_packed_path,
        "seeds": seeds,
        "artifact_entities": artifact_entities,
        "summary": summary,
        "dispatch_payload": dispatch_payload,
    }
