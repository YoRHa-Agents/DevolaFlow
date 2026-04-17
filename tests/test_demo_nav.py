"""Tests for demo nav.js landing-page detection.

Regression guard for v7.1.0-pre feedback "github 上的所有次级网页无法访问".

The bug: ``workflow-system/human/demo/shared/nav.js`` previously detected
the landing page by matching ``/demo/`` in ``window.location.pathname``.
GitHub Pages deploys the demo at ``/DevolaFlow/`` (not ``/demo/``), so on
the deployed landing page ``isLanding`` evaluated to ``False`` and every
nav link was prefixed with ``../`` — producing 404s outside the project.

The fix detects landing by the ABSENCE of any known sub-page directory
name in the URL path, so it works under all deployment shapes (GitHub
Pages, project-root local server, demo-dir local server, ``file://``).

These tests reimplement the JS predicate in Python after extracting
``SUBPAGE_DIRS`` directly from ``nav.js`` — no browser, no playwright.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

NAV_JS_PATH = Path("workflow-system/human/demo/shared/nav.js")
DEMO_DIR = Path("workflow-system/human/demo")


def _read_nav_js(project_root: Path) -> str:
    return (project_root / NAV_JS_PATH).read_text(encoding="utf-8")


def _extract_subpage_dirs(nav_js_text: str) -> list[str]:
    """Parse the SUBPAGE_DIRS array literal out of nav.js.

    Matches the block:

        var SUBPAGE_DIRS = [
          'a', 'b', ...
        ];
    """
    match = re.search(
        r"var\s+SUBPAGE_DIRS\s*=\s*\[(.*?)\]\s*;",
        nav_js_text,
        re.DOTALL,
    )
    assert match, "SUBPAGE_DIRS not found in nav.js"
    body = match.group(1)
    return re.findall(r"'([^']+)'", body)


def _is_landing(url_path: str, subpage_dirs: list[str]) -> bool:
    """Python reimplementation of the ``isLanding`` IIFE in nav.js.

    Mirrors the JS exactly:

        return !SUBPAGE_DIRS.some(function (d) {
          return path.indexOf('/' + d + '/') !== -1 ||
                 path.endsWith('/' + d);
        });
    """
    for d in subpage_dirs:
        if ("/" + d + "/") in url_path:
            return False
        if url_path.endswith("/" + d):
            return False
    return True


def _path_only(url: str) -> str:
    """Strip scheme + authority to get just the path component (mimics
    ``window.location.pathname``)."""
    if url.startswith("file://"):
        return url[len("file://") :]
    if "://" in url:
        rest = url.split("://", 1)[1]
        slash_idx = rest.find("/")
        if slash_idx == -1:
            return "/"
        return rest[slash_idx:]
    return url


@pytest.fixture
def subpage_dirs(project_root: Path) -> list[str]:
    return _extract_subpage_dirs(_read_nav_js(project_root))


URL_CASES: list[tuple[str, bool]] = [
    # GitHub Pages (deployed at /DevolaFlow/)
    ("https://yorha-agents.github.io/DevolaFlow/", True),
    ("https://yorha-agents.github.io/DevolaFlow/index.html", True),
    ("https://yorha-agents.github.io/DevolaFlow/design-system/", False),
    ("https://yorha-agents.github.io/DevolaFlow/design-system/index.html", False),
    ("https://yorha-agents.github.io/DevolaFlow/framework-chain/", False),
    ("https://yorha-agents.github.io/DevolaFlow/context-flow/", False),
    ("https://yorha-agents.github.io/DevolaFlow/version-timeline/", False),
    ("https://yorha-agents.github.io/DevolaFlow/design-architecture/", False),
    ("https://yorha-agents.github.io/DevolaFlow/workflow-visualizer/", False),
    ("https://yorha-agents.github.io/DevolaFlow/stage-explorer/", False),
    ("https://yorha-agents.github.io/DevolaFlow/benchmark-results/", False),
    # Local server rooted at the demo directory
    ("http://localhost:8000/", True),
    ("http://localhost:8000/index.html", True),
    # Local server rooted at the project root (legacy /demo/ shape)
    ("http://localhost:8000/demo/index.html", True),
    ("http://localhost:8000/demo/design-system/index.html", False),
    # file:// direct open
    ("file:///x/workflow-system/human/demo/index.html", True),
    ("file:///x/workflow-system/human/demo/design-system/index.html", False),
]


@pytest.mark.parametrize("url,expected_is_landing", URL_CASES)
def test_is_landing_for_url_shape(
    url: str,
    expected_is_landing: bool,
    subpage_dirs: list[str],
) -> None:
    """For each canonical URL shape, the JS-equivalent ``isLanding``
    predicate must return the expected value."""
    path = _path_only(url)
    actual = _is_landing(path, subpage_dirs)
    assert actual is expected_is_landing, (
        f"isLanding({url!r}) returned {actual}, expected {expected_is_landing} "
        f"(parsed path={path!r}, subpage_dirs={subpage_dirs})"
    )


def test_url_cases_cover_all_required_shapes() -> None:
    """Sanity check — the parametrized list must cover the 17 URL
    shapes mandated by the v7.1.1 hotfix spec (≥17 assertions)."""
    assert len(URL_CASES) >= 17, f"URL_CASES has only {len(URL_CASES)} entries; spec requires ≥17"


def test_subpage_dirs_match_disk_layout(project_root: Path) -> None:
    """SUBPAGE_DIRS in nav.js must exactly match the on-disk sub-page
    directories under workflow-system/human/demo/ (excluding shared/)."""
    nav_js = _read_nav_js(project_root)
    declared = sorted(_extract_subpage_dirs(nav_js))

    demo_root = project_root / DEMO_DIR
    on_disk = sorted(p.name for p in demo_root.iterdir() if p.is_dir() and p.name != "shared")

    assert declared == on_disk, (
        f"SUBPAGE_DIRS in nav.js {declared} does not match on-disk "
        f"sub-page directories {on_disk}. If a directory was added or "
        f"removed under {DEMO_DIR}/, update SUBPAGE_DIRS in nav.js to "
        f"match (and adjust this test if the layout intentionally changed)."
    )


def test_subpage_dirs_count_is_eight(project_root: Path) -> None:
    """SUBPAGE_DIRS must contain exactly 8 entries (matches v7.1.0 demo layout)."""
    declared = _extract_subpage_dirs(_read_nav_js(project_root))
    assert len(declared) == 8, f"Expected 8 sub-page directories, got {len(declared)}: {declared}"


def test_legacy_demo_only_detection_was_replaced(project_root: Path) -> None:
    """Regression guard: nav.js must NOT contain the old '/demo/'-only
    isLanding check that broke GitHub Pages."""
    nav_js = _read_nav_js(project_root)
    bad_pattern = re.compile(
        r"path\.endsWith\(\s*['\"]/demo/['\"]\s*\)\s*\|\|\s*"
        r"path\.endsWith\(\s*['\"]/demo/index\.html['\"]\s*\)",
        re.DOTALL,
    )
    assert not bad_pattern.search(nav_js), (
        "nav.js still contains the legacy '/demo/'-only isLanding "
        "predicate that 404'd on GitHub Pages — see "
        ".local/feedbacks/feedback_for_v7.1.0-pre.md"
    )
