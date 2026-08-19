"""Drift detection for compiled rule outputs.

v15.0.0 (clean_repo C1-2, decision D1): the v9.0.0 PV-07 stub-drift
machinery — the deprecated-stub registry plus its fingerprint compute
and check helpers — was retired together with the six deprecated
`.cursor/rules/` pointer stubs it pinned. Drift protection now covers
exactly the compiled targets declared in
``.rules/compile-config.yaml``; the reverse lint in
``tests/ghost/test_rules.py::test_rule_surfaces_compile_only``
prevents stub resurrection.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DriftResult:
    target: str
    status: str  # "in_sync" | "drifted" | "missing"
    expected_hash: str
    actual_hash: str


def _file_hash(path: Path) -> str:
    """SHA-256 prefix of a file's content, or empty string if missing."""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def save_hashes(results: list[Any], hash_file: str | Path) -> None:
    """Persist compile result hashes to a JSON file.

    Args:
        results: List of CompileResult objects (or anything with
                 .target and .content_hash).
        hash_file: Path to the JSON hash store.
    """
    hash_file = Path(hash_file)
    hash_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, str] = {r.target: r.content_hash for r in results}

    hash_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_rules_drift(
    rules_dir: str | Path,
    config_path: str | Path | None = None,
) -> list[DriftResult]:
    """Compare compiled files against stored hashes.

    Args:
        rules_dir: Path to the .rules/ directory.
        config_path: Path to compile-config.yaml. Defaults to
                     ``rules_dir / compile-config.yaml``.

    Returns:
        List of DriftResult per target.
    """
    rules_dir = Path(rules_dir)
    config_path = Path(config_path) if config_path else rules_dir / "compile-config.yaml"

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    drift_cfg = raw.get("drift_detection", {})
    repo_root = rules_dir.parent
    hash_file_rel = Path(drift_cfg.get("hash_file", ".rules/.compile-hashes.json"))
    hash_file = repo_root / hash_file_rel

    stored: dict[str, str] = {}
    if hash_file.exists():
        stored = json.loads(hash_file.read_text(encoding="utf-8"))

    results: list[DriftResult] = []
    for target_name, target_spec in raw.get("targets", {}).items():
        output_path = rules_dir.parent / target_spec["output"]
        expected = stored.get(target_name, "")
        actual = _file_hash(output_path)

        if not output_path.exists():
            status = "missing"
        elif actual == expected:
            status = "in_sync"
        else:
            status = "drifted"

        results.append(
            DriftResult(
                target=target_name,
                status=status,
                expected_hash=expected,
                actual_hash=actual,
            )
        )

    return results
