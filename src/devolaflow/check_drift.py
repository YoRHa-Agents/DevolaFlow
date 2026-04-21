"""Drift detection -- compare agent source versions vs human doc versions.

Design ref: design_dual_system.md section 4.4

v8.0.0 (P-11) — thin wrapper over :class:`devolaflow.entropy_manager.DeviationScanner`.
The public :func:`check_drift` / :func:`_parse_frontmatter` / :func:`_find_project_root`
API is preserved byte-for-byte for existing callers (``devola-check-drift`` CLI,
``tests/test_exercise_modules.py``).
"""

from __future__ import annotations

from pathlib import Path

from devolaflow.entropy_manager import DeviationScanner
from devolaflow.entropy_manager import _parse_frontmatter as _em_parse_frontmatter


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file.

    Retained as a module-level helper for backward compatibility with any
    caller importing ``devolaflow.check_drift._parse_frontmatter``.
    """
    return _em_parse_frontmatter(path)


def _find_project_root() -> Path:
    """Walk up from the current file to find the project root containing pyproject.toml."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    return Path.cwd()


def check_drift() -> bool:
    """Check human docs for drift against agent source. Returns True if drift found.

    Delegates to :class:`devolaflow.entropy_manager.DeviationScanner` so the
    underlying logic stays single-sourced. The printed output and boolean
    return value match the pre-v8 implementation exactly.
    """
    scanner = DeviationScanner(project_root=_find_project_root())
    return scanner.print_report()
