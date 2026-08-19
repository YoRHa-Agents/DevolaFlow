"""Loader for the install-manifest SSOT (``workflow-system/agent/manifest.yaml``).

The manifest is the single owner (Rule A-5) of the per-tool install file
lists. This module is the canonical Python read path; consumers
(``devola-init`` via :mod:`devolaflow.init_project`, the
``scripts/sync_cursor_skill.py`` mirror) resolve WHAT to install through
:func:`load_manifest` + :func:`profile_files` instead of keeping local
copies of the lists (Rule A-5.1). ``scripts/install.sh`` reads the same
YAML with a line-oriented shell parser — the manifest's flat-list layout
is a load-bearing contract shared with that parser.

Three-way parity (manifest ↔ on-disk files ↔ ``_SF4_REFERENCE_SET``) is
linted by ``tests/test_install_manifest.py``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

MANIFEST_FILENAME = "manifest.yaml"

#: Top-level file-list sections a valid manifest must define.
SECTION_KEYS: tuple[str, ...] = ("core", "references", "examples")


class ManifestError(ValueError):
    """Raised when the install manifest is missing or structurally invalid.

    Explicit error state per Rule S-5 — consumers decide whether to
    degrade (WARN + fallback) or abort; the loader never guesses.
    """


def load_manifest(agent_dir: Path | str) -> dict[str, Any]:
    """Load and validate ``<agent_dir>/manifest.yaml``.

    Returns the parsed mapping. Raises :class:`ManifestError` when the
    file is absent, unparseable, or missing a required section — never
    returns a partially-valid manifest.
    """
    path = Path(agent_dir) / MANIFEST_FILENAME
    if not path.is_file():
        raise ManifestError(f"install manifest missing: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ManifestError(f"install manifest unparseable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"install manifest root must be a mapping: {path}")

    for key in SECTION_KEYS:
        entries = data.get(key)
        if not isinstance(entries, list) or not entries:
            raise ManifestError(f"install manifest section {key!r} must be a non-empty list")
        bad = [e for e in entries if not isinstance(e, str)]
        if bad:
            raise ManifestError(f"install manifest section {key!r} has non-string entries: {bad}")

    profiles = data.get("install_profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ManifestError("install manifest must define a non-empty 'install_profiles' mapping")
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ManifestError(f"install profile {name!r} must be a mapping")
        sets = profile.get("sets")
        if not isinstance(sets, list) or not sets:
            raise ManifestError(f"install profile {name!r} must declare a non-empty 'sets' list")
        unknown = [s for s in sets if s not in SECTION_KEYS]
        if unknown:
            raise ManifestError(
                f"install profile {name!r} references undefined sets {unknown}; "
                f"valid sets: {list(SECTION_KEYS)}"
            )
    return data


def profile_files(manifest: dict[str, Any], profile: str) -> list[str]:
    """Resolve *profile* to its ordered file list (agent-dir-relative paths).

    Raises :class:`ManifestError` for an unknown profile so callers get an
    explicit error state (Rule S-5) instead of an empty install.
    """
    profiles = manifest["install_profiles"]
    if profile not in profiles:
        raise ManifestError(f"unknown install profile {profile!r}; available: {sorted(profiles)}")
    files: list[str] = []
    for set_name in profiles[profile]["sets"]:
        files.extend(manifest[set_name])
    return files
