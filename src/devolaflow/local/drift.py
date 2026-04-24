"""Drift detection for compiled rule outputs.

v9.0.0 PV-07 (ADR-007 D2 + D5) extension:

* :func:`check_stub_drift` — verifies the v9.0.0-deprecated
  ``.cursor/rules/{devola-flow,workflow}-rules.mdc`` stubs match the
  expected stub-template content (a hand-edit to either stub fails the
  drift check). Used by
  ``tests/test_no_ghost_features.py::test_rule_surfaces_compile_only``.
* :data:`DEPRECATED_STUB_FILES` — tuple of the 2 deprecated stub paths
  enforced by the drift check. Adding a new deprecated stub requires
  adding the path here AND providing its expected SHA-256 fingerprint
  in ``.rules/.compile-hashes.json`` under the matching key.
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


# v9.0.0 PV-07 (ADR-007 D2): the 2 deprecated cursor-rule stubs
# whose ≤ 50-line cross-reference scaffold content is pinned by the
# drift detector. The expected hash for each lives under the matching
# ``stub_<name>`` key in .rules/.compile-hashes.json.
DEPRECATED_STUB_FILES: tuple[tuple[str, str], ...] = (
    ("stub_devola_flow_rules", ".cursor/rules/devola-flow-rules.mdc"),
    ("stub_workflow_rules", ".cursor/rules/workflow-rules.mdc"),
)


def _file_hash(path: Path) -> str:
    """SHA-256 prefix of a file's content, or empty string if missing."""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def compute_stub_fingerprints(repo_root: Path) -> dict[str, str]:
    """Compute SHA-256 fingerprints for every deprecated cursor-rule stub.

    v9.0.0 PV-07 (ADR-007 D2): the 2 deprecated stubs
    (`.cursor/rules/devola-flow-rules.mdc` + `.cursor/rules/workflow-rules.mdc`)
    are the cross-reference scaffolds that point operators at the
    canonical `.rules/` source. The fingerprints below pin their content
    so any hand-edit fails ``check_stub_drift``.

    Returns a dict keyed by the stub's ``key`` (from
    :data:`DEPRECATED_STUB_FILES`) to the hash. Missing files return
    an empty-string hash so the caller can distinguish "missing" from
    "drifted".
    """
    return {key: _file_hash(repo_root / relpath) for key, relpath in DEPRECATED_STUB_FILES}


def save_hashes(
    results: list[Any],
    hash_file: str | Path,
    *,
    repo_root: Path | None = None,
) -> None:
    """Persist compile result hashes to a JSON file.

    Args:
        results: List of CompileResult objects (or anything with
                 .target and .content_hash).
        hash_file: Path to the JSON hash store.
        repo_root: Optional repo root for v9.0.0 PV-07 stub fingerprints.
                   When provided, the stored JSON includes ``stub_*`` keys
                   matching :func:`compute_stub_fingerprints` so
                   :func:`check_stub_drift` has fingerprints to compare
                   against. When omitted, falls back to ``hash_file``'s
                   2nd parent (the .rules/ folder's parent — i.e., repo
                   root for the canonical layout).
    """
    hash_file = Path(hash_file)
    hash_file.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, str] = {r.target: r.content_hash for r in results}

    if repo_root is None:
        # Default: hash_file's grandparent. For .rules/.compile-hashes.json
        # this is the repo root.
        repo_root = hash_file.parent.parent

    stubs = compute_stub_fingerprints(repo_root)
    for key, fingerprint in stubs.items():
        if fingerprint:
            data[key] = fingerprint

    hash_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def check_stub_drift(
    repo_root: Path,
    hash_file: str | Path | None = None,
) -> list[DriftResult]:
    """Verify the v9.0.0-deprecated cursor-rule stubs match stored hashes.

    v9.0.0 PV-07 (ADR-007 D2 + D5): the 2 deprecated stubs
    (`.cursor/rules/devola-flow-rules.mdc` + `.cursor/rules/workflow-rules.mdc`)
    are pinned cross-reference scaffolds. A hand-edit to either stub
    fails this drift check; CI enforcement lives in
    ``tests/test_no_ghost_features.py::test_rule_surfaces_compile_only``.

    Args:
        repo_root: Path to the repository root (parent of ``.cursor/`` and
                   ``.rules/``).
        hash_file: Path to the JSON hash store. Defaults to
                   ``<repo_root>/.rules/.compile-hashes.json``.

    Returns:
        List of DriftResult per deprecated stub. Status is one of
        ``"in_sync"`` (actual hash matches stored), ``"drifted"``
        (actual differs from stored), or ``"missing"`` (file or stored
        hash absent).
    """
    repo_root = Path(repo_root)
    hash_file = Path(hash_file) if hash_file else repo_root / ".rules" / ".compile-hashes.json"

    stored: dict[str, str] = {}
    if hash_file.exists():
        stored = json.loads(hash_file.read_text(encoding="utf-8"))

    results: list[DriftResult] = []
    for key, relpath in DEPRECATED_STUB_FILES:
        stub_path = repo_root / relpath
        expected = stored.get(key, "")
        actual = _file_hash(stub_path)

        if not stub_path.exists() or not expected:
            status = "missing"
        elif actual == expected:
            status = "in_sync"
        else:
            status = "drifted"

        results.append(
            DriftResult(
                target=key,
                status=status,
                expected_hash=expected,
                actual_hash=actual,
            )
        )

    return results


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
