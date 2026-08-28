#!/usr/bin/env python3
"""Hard-fail CJK lint for agent-facing prompt surfaces."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Final

CJK_RE: Final[re.Pattern[str]] = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

# This is the complete inventory of repository surfaces that can be consumed
# as agent instructions or used to construct an agent prompt. Keep paths
# repository-relative and add new surfaces here rather than relying on a
# caller to remember an extra scan.
DEFAULT_TARGETS: Final[tuple[str, ...]] = (
    "AGENTS.md",
    ".rules",
    ".cursor/skills",
    ".cursor/rules",
    "workflow-system/agent",
    "schemas",
    ".github/copilot-instructions.md",
    "src/devolaflow/task_adaptive_selector.py",
    "src/devolaflow/harness",
    "tests/fixtures/harness",
)

# Copilot output is a generated, ignored consumer artifact. Its absence is
# valid, but an unknown or unexpectedly missing inventory path is not.
OPTIONAL_TARGETS: Final[frozenset[str]] = frozenset({".github/copilot-instructions.md"})
GENERATED_OPTIONAL_TARGETS: Final[frozenset[str]] = OPTIONAL_TARGETS

# These are explicit Q6 exemptions. They apply only when a caller includes
# the corresponding surface in a custom target set; they are not a broad
# exclusion from the default inventory.
Q6_EXEMPT_PREFIXES: Final[tuple[str, ...]] = (
    "workflow-system/human/",
    "docs/cycle-archive/",
    ".local/",
)

# The install skill intentionally carries bilingual activation phrases. The
# line number and an identifying English/Chinese phrase are both checked so
# a future unrelated CJK line cannot inherit the exemption accidentally.
TRIGGER_EXEMPTION_LINES: Final[dict[str, dict[int, str]]] = {
    ".cursor/skills/install-devola-flow/SKILL.md": {
        11: "Chinese phrasings",
        12: "把 devola 装到 cursor",
        13: "全局安装 devola 到 cursor 和 claude",
        37: "安装 devola-flow",
        38: "全局安装 devola-flow",
        39: "升级 devola",
        41: "把 devola 装到 cursor",
        43: "把 devola 装到 claude",
        44: "全局安装 devola 到 cursor 和 claude",
    }
}

# Test fixtures may contain representative bilingual prompt data only when
# they opt in with this marker in their first eight lines.
FIXTURE_EXEMPTION_MARKER: Final[str] = "devolaflow: allow-cjk"
FIXTURE_PREFIX: Final[str] = "tests/fixtures/"
IGNORED_GENERATED_PARTS: Final[frozenset[str]] = frozenset({"__pycache__"})
IGNORED_GENERATED_SUFFIXES: Final[frozenset[str]] = frozenset({".pyc", ".pyo"})


def _relative_target(target: str) -> Path:
    """Validate and normalize one repository-relative inventory target."""
    path = Path(target)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"language inventory target must be repository-relative: {target!r}")
    return path


def _is_exempt_prefix(relative_path: str) -> bool:
    """Return whether a path belongs to an explicitly exempt Q6 surface."""
    return any(
        relative_path == prefix.rstrip("/") or relative_path.startswith(prefix)
        for prefix in Q6_EXEMPT_PREFIXES
    )


def _is_marked_fixture(relative_path: str, lines: list[str]) -> bool:
    """Return whether a test fixture opts into the narrow CJK exemption."""
    return relative_path.startswith(FIXTURE_PREFIX) and any(
        FIXTURE_EXEMPTION_MARKER in line for line in lines[:8]
    )


def _is_exempt_trigger(relative_path: str, line_number: int, line: str) -> bool:
    """Return whether one exact intentional install-trigger line is exempt."""
    expected = TRIGGER_EXEMPTION_LINES.get(relative_path, {}).get(line_number)
    return expected is not None and expected in line


def _is_untracked_generated_target(root: Path, target: str) -> bool:
    """Return whether an optional generated artifact is outside repository state."""
    if target not in GENERATED_OPTIONAL_TARGETS:
        return False
    try:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", target],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot determine tracked state for {target}: {exc}") from exc
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    # A non-repository root is not evidence that the target is generated.
    if result.returncode == 128 and not (root / ".git").exists():
        return False
    raise RuntimeError(
        f"cannot determine tracked state for {target}: git ls-files exited {result.returncode}"
    )


def find_cjk(root: Path, targets: tuple[str, ...] = DEFAULT_TARGETS) -> list[str]:
    """Return relative locations containing CJK characters."""
    findings = []
    for target in targets:
        normalized_target = _relative_target(target)
        path = root / normalized_target
        if not path.exists():
            if target in OPTIONAL_TARGETS:
                continue
            raise FileNotFoundError(
                f"language inventory target is missing: {normalized_target.as_posix()}"
            )
        if _is_untracked_generated_target(root, target):
            continue
        paths = [path] if path.is_file() else sorted(path.rglob("*"))
        for file_path in paths:
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(root).as_posix()
            if (
                any(part in IGNORED_GENERATED_PARTS for part in file_path.relative_to(root).parts)
                or file_path.suffix in IGNORED_GENERATED_SUFFIXES
            ):
                continue
            lines = file_path.read_text(encoding="utf-8").splitlines()
            for line_number, line in enumerate(lines, start=1):
                if (
                    CJK_RE.search(line)
                    and not _is_exempt_prefix(relative_path)
                    and not _is_marked_fixture(relative_path, lines)
                    and not _is_exempt_trigger(relative_path, line_number, line)
                ):
                    findings.append(f"{relative_path}:{line_number}")
    return findings


def main(argv: list[str] | None = None) -> int:
    """Run the agent-facing language lint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    findings = find_cjk(args.root)
    if findings:
        print("FAIL: CJK characters found in agent-facing files")
        print("\n".join(f"  {finding}" for finding in findings))
        return 1
    print("PASS: agent-facing files are English-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
