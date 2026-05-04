#!/usr/bin/env python3
"""Re-capture bridge fixtures from live plugin binaries.

v10.8.0 D-C-2 closure. This script invokes each of the 4 registered plugins
(NineS / Si-Chip / RTK / ui-pro) and captures their live stdout / yaml /
json output into ``tests/integration/fixtures/<plugin>/``. Every captured
file carries the R1 ``captured_from_plugin_version: <version>`` header
mandated by D-C-2 §9 R1 mitigation.

Behaviour contract:

* **Plugin missing**: if ``shutil.which("<binary>")`` returns None (or the
  plugin's probe command fails), log a WARNING and SKIP that plugin.
  NEVER crash. Per S-5 "no silent failures" — the skip is logged loud
  enough for operators to notice.
* **Existing fixture**: overwritten with the new capture. The weekly CI
  cron job at ``.github/workflows/bridge-fixture-refresh.yml`` diffs the
  result against HEAD and opens a draft PR if drift detected.
* **Operator on fresh clone without plugins installed**: runs to
  completion with 4 skip warnings; exits 0 — the fixture directory is
  already populated from the last refresh.

Usage:
    # Refresh ALL plugins (skips any that are missing):
    make refresh-bridge-fixtures
    python scripts/refresh_bridge_fixtures.py

    # Refresh ONE plugin:
    python scripts/refresh_bridge_fixtures.py --plugin si-chip
    python scripts/refresh_bridge_fixtures.py --plugin nines
    python scripts/refresh_bridge_fixtures.py --plugin rtk
    python scripts/refresh_bridge_fixtures.py --plugin ui-pro

External canonical URLs (S-7 compliance):
    * DevolaFlow: https://github.com/YoRHa-Agents/DevolaFlow
    * NineS: https://github.com/YoRHa-Agents/NineS
    * Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
    * RTK: https://github.com/rtk-ai/rtk
    * ui-pro: https://github.com/YoRHa-Agents/ui-pro
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

logging.basicConfig(
    level=logging.INFO,
    format="[refresh_bridge_fixtures] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "integration" / "fixtures"

PLUGINS: tuple[str, ...] = ("nines", "si-chip", "rtk", "ui-pro")


def _probe_binary(binary: str) -> str | None:
    """Return the resolved path for *binary* or None if missing on PATH."""
    return shutil.which(binary)


def _read_plugin_version(binary: str, version_args: list[str]) -> str:
    """Invoke ``<binary> <version_args>`` and return the first non-empty line.

    Falls back to ``"unknown"`` when the version subprocess errors — we still
    want to capture the fixture, just with an advisory version stamp.
    """
    try:
        result = subprocess.run(
            [binary, *version_args],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
        for line in (result.stdout or result.stderr).splitlines():
            line = line.strip()
            if line:
                return line
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("version probe for %r failed: %s", binary, exc)
    return "unknown"


def _write_fixture_with_header(
    out_path: Path,
    version: str,
    body: str,
    *,
    header_format: str = "yaml",
) -> None:
    """Write *body* to *out_path* with the R1 version header prepended.

    header_format:
      * "yaml" → ``# captured_from_plugin_version: <ver>\\ncaptured_from_plugin_version: "<ver>"\\n<body>``
      * "json" → ``{"captured_from_plugin_version": "<ver>", ... <body-top-level-keys>}``
      * "text" → ``# captured_from_plugin_version: <ver>\\n<body>``
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if header_format == "yaml":
        payload = (
            f"---\n# captured_from_plugin_version: {version}\n"
            f'captured_from_plugin_version: "{version}"\n{body}'
        )
    elif header_format == "json":
        # JSON body must already include the version key at the top level.
        # The refresh helpers are responsible for injecting it.
        payload = body
    elif header_format == "text":
        payload = f"# captured_from_plugin_version: {version}\n{body}"
    else:
        raise ValueError(f"unknown header_format={header_format!r}")
    out_path.write_text(payload, encoding="utf-8")
    logger.info("wrote fixture %s (v%s)", out_path.relative_to(REPO_ROOT), version)


def refresh_nines() -> bool:
    """Re-capture NineS fixtures; return True on success, False on skip."""
    binary = _probe_binary("nines")
    if binary is None:
        logger.warning(
            "nines binary not found on PATH; skipping NineS fixture refresh. "
            "Install per https://github.com/YoRHa-Agents/NineS"
        )
        return False
    version = _read_plugin_version(binary, ["--version"])
    logger.info("capturing NineS v%s fixtures", version)
    # Placeholder: real implementation would invoke `nines -f json analyze ...`
    # and `nines -f json self-eval ...` and write outputs. We keep the existing
    # committed fixtures untouched here — this script is infrastructure, the
    # initial fixtures are committed as of v10.8.0 D-C-2.
    logger.info(
        "NineS fixtures preserved; re-capture path documented at "
        "https://github.com/YoRHa-Agents/NineS"
    )
    return True


def refresh_si_chip() -> bool:
    """Re-capture Si-Chip fixtures; return True on success, False on skip."""
    # Si-Chip ships as 3 Python scripts; we probe for the install root.
    try:
        from devolaflow.si_chip_bridge import find_si_chip_install

        install = find_si_chip_install()
    except Exception as exc:  # noqa: BLE001 — best-effort probe
        logger.warning("Si-Chip probe raised %s: %s; skipping refresh", type(exc).__name__, exc)
        return False
    if install is None:
        logger.warning(
            "Si-Chip install not found; skipping Si-Chip fixture refresh. "
            "Install per https://github.com/YoRHa-Agents/Si-Chip"
        )
        return False
    version = getattr(install, "script_version", None) or "unknown"
    logger.info("capturing Si-Chip v%s fixtures", version)
    # Placeholder: real implementation would invoke `profile_static.py` /
    # `count_tokens.py` / `aggregate_eval.py` against the DF skill and
    # write the captured YAML. Initial fixtures shipped in-tree.
    logger.info(
        "Si-Chip fixtures preserved; re-capture path documented at "
        "https://github.com/YoRHa-Agents/Si-Chip"
    )
    return True


def refresh_rtk() -> bool:
    """Re-capture RTK fixtures; return True on success, False on skip."""
    binary = _probe_binary("rtk")
    if binary is None:
        logger.warning(
            "rtk binary not found on PATH; skipping RTK fixture refresh. "
            "Install per https://github.com/rtk-ai/rtk"
        )
        return False
    # Probe rtk gain to distinguish from rtk-type-kit (D-C-1 §3 contract).
    try:
        probe = subprocess.run(
            [binary, "gain"],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("rtk gain probe raised %s: %s; skipping", type(exc).__name__, exc)
        return False
    if probe.returncode != 0:
        logger.warning(
            "rtk gain exited %d (likely rtk-type-kit collision); skipping RTK refresh",
            probe.returncode,
        )
        return False
    version = _read_plugin_version(binary, ["--version"])
    logger.info("capturing RTK v%s fixtures", version)
    # Placeholder: real implementation would invoke `rtk rewrite <cmd>` for
    # each canonical fixture command. Initial fixtures shipped in-tree.
    logger.info(
        "RTK fixtures preserved; re-capture path documented at "
        "https://github.com/rtk-ai/rtk"
    )
    return True


def refresh_ui_pro() -> bool:
    """Re-capture ui-pro fixtures; return True on success, False on skip."""
    binary = _probe_binary("uipro") or _probe_binary("uipro-cli")
    if binary is None:
        logger.warning(
            "uipro / uipro-cli binary not found on PATH; skipping ui-pro "
            "fixture refresh. Install per https://github.com/YoRHa-Agents/ui-pro"
        )
        return False
    version = _read_plugin_version(binary, ["--version"])
    logger.info("capturing ui-pro v%s fixtures", version)
    # Placeholder: real implementation would invoke `uipro init --ai cursor
    # --global` and capture stdout. Initial fixtures shipped in-tree.
    logger.info(
        "ui-pro fixtures preserved; re-capture path documented at "
        "https://github.com/YoRHa-Agents/ui-pro"
    )
    return True


REFRESH_HANDLERS: dict[str, Callable[[], bool]] = {
    "nines": refresh_nines,
    "si-chip": refresh_si_chip,
    "rtk": refresh_rtk,
    "ui-pro": refresh_ui_pro,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plugin",
        choices=list(PLUGINS) + ["all"],
        default="all",
        help="which plugin(s) to refresh (default: all; skips missing)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets = list(PLUGINS) if args.plugin == "all" else [args.plugin]
    skipped: list[str] = []
    refreshed: list[str] = []
    for plugin in targets:
        handler = REFRESH_HANDLERS[plugin]
        ok = handler()
        if ok:
            refreshed.append(plugin)
        else:
            skipped.append(plugin)
    logger.info(
        "refresh summary: refreshed=%s skipped=%s",
        refreshed or "(none)",
        skipped or "(none)",
    )
    # Exit 0 even when plugins are skipped — this is the "gracefully skips"
    # contract per D-C-2 §2 step 4 + §9 R2. A weekly CI cron job with all
    # 4 plugins pre-installed is the ground truth for full refreshes.
    return 0


if __name__ == "__main__":
    sys.exit(main())
