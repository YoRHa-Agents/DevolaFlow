"""Tests for ``scripts/detect_dead_apis.py`` — the dead-wire CI guard.

The detector catches the bug class that cost the v6.0.x line three versions
to fix: a public function with passing unit tests but ZERO production
callers (``apply_round_escalation`` and ``merge_reinforcement_into_dispatch``
in v5.3.0 → v6.0.3).

The headline test is :func:`test_devolaflow_codebase_has_no_dead_apis`,
which runs the detector against the live ``src/devolaflow/`` tree and
asserts the dead list is empty (modulo the documented allowlist). The
synthetic tests pin down the detector's individual rules so the BIG test
fails for the right reason when something regresses.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "detect_dead_apis.py"


def _load_detector_module() -> Any:
    """Import ``scripts/detect_dead_apis.py`` as a module without polluting sys.path."""
    mod_name = "_detect_dead_apis"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


detect = _load_detector_module()


def _write_src(tmp_path: Path, name: str, body: str) -> Path:
    """Create ``tmp_path/src/<pkg>/<name>.py`` with the given body."""
    src_pkg = tmp_path / "src" / "fake"
    src_pkg.mkdir(parents=True, exist_ok=True)
    init = src_pkg / "__init__.py"
    if not init.exists():
        init.write_text("")
    f = src_pkg / name
    f.write_text(body)
    return f


def _write_test(tmp_path: Path, name: str, body: str) -> Path:
    """Create ``tmp_path/tests/<name>.py`` with the given body."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    f = tests_dir / name
    f.write_text(body)
    return f


def test_detect_dead_apis_finds_unused_function(tmp_path: Path) -> None:
    """A public function with no caller anywhere (only a test) is flagged."""
    _write_src(tmp_path, "mod_a.py", "def unused_helper():\n    return 1\n")
    _write_test(
        tmp_path,
        "test_a.py",
        "from fake.mod_a import unused_helper\n\ndef test_x():\n    assert unused_helper() == 1\n",
    )

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "unused_helper" in names


def test_detect_dead_apis_ignores_used_function(tmp_path: Path) -> None:
    """A public function called from another src file is NOT flagged.

    The caller (``run``) is itself unused so it would be flagged; what we
    care about here is that ``used_helper`` is NOT flagged because
    ``run`` references it.
    """
    _write_src(tmp_path, "mod_b.py", "def used_helper():\n    return 2\n")
    _write_src(
        tmp_path,
        "mod_caller.py",
        (
            "from fake.mod_b import used_helper\n\n"
            "def run():\n"
            "    return used_helper()\n\n"
            "ENTRY = run\n"
        ),
    )

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "used_helper" not in names
    assert "run" not in names, "run is referenced by the module-level ENTRY assignment"


def test_detect_dead_apis_ignores_test_callers(tmp_path: Path) -> None:
    """Tests do not count as production callers — the v6.0.3 bug class."""
    _write_src(tmp_path, "mod_c.py", "def only_tested():\n    return 3\n")
    _write_test(
        tmp_path,
        "test_c.py",
        (
            "from fake.mod_c import only_tested\n\n"
            "def test_x():\n"
            "    assert only_tested() == 3\n"
            "    assert only_tested() == 3\n"
        ),
    )

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "only_tested" in names, "test-only callers should not save a symbol"


def test_detect_dead_apis_respects_allowlist(tmp_path: Path) -> None:
    """An allowlisted symbol is suppressed even when it has no callers."""
    _write_src(tmp_path, "mod_d.py", "def public_external():\n    return 4\n")

    qualified = "fake.mod_d:public_external"
    dead_no_allow = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    dead_allow = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist={qualified},
    )
    assert any(d.symbol.qualified == qualified for d in dead_no_allow)
    assert all(d.symbol.qualified != qualified for d in dead_allow)


def test_detect_dead_apis_skips_private(tmp_path: Path) -> None:
    """Names starting with ``_`` (including ``__dunder__``) are never reported."""
    _write_src(
        tmp_path,
        "mod_e.py",
        (
            "def _private_helper():\n    return 5\n\n"
            "def __dunder_like__():\n    return 6\n\n"
            "class _PrivateCls:\n    pass\n"
        ),
    )

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "_private_helper" not in names
    assert "__dunder_like__" not in names
    assert "_PrivateCls" not in names


def test_detect_dead_apis_skips_cli_entries(tmp_path: Path) -> None:
    """CLI entry-point conventions (`main`, `cli`, `*_cmd`) are skipped."""
    _write_src(
        tmp_path,
        "mod_f.py",
        (
            "def main():\n    return 0\n\n"
            "def cli():\n    return 0\n\n"
            "def version_cmd():\n    return 0\n\n"
            "def build_cmd():\n    return 0\n"
        ),
    )

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "main" not in names
    assert "cli" not in names
    assert "version_cmd" not in names
    assert "build_cmd" not in names


def test_detect_dead_apis_treats_init_reexport_as_non_caller(tmp_path: Path) -> None:
    """A symbol that only appears in an ``__init__.py`` re-export is still dead.

    This is the exact regression that hid the v6.0.3 dead-wire bug:
    ``findings_to_reinforcement`` was re-exported via ``gate/__init__.py``
    but no production code ever called it.
    """
    _write_src(tmp_path, "mod_g.py", "def reexported_only():\n    return 7\n")
    init = tmp_path / "src" / "fake" / "__init__.py"
    init.write_text("from fake.mod_g import reexported_only\n")

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "reexported_only" in names, "pure re-export must not satisfy the caller check"


def test_detect_dead_apis_counts_self_use_as_alive(tmp_path: Path) -> None:
    """A class instantiated within its own defining file counts as alive."""
    body = (
        "class SelfReferenced:\n"
        "    def __init__(self, value=0):\n"
        "        self.value = value\n\n"
        "DEFAULT = SelfReferenced(1)\n"
    )
    _write_src(tmp_path, "mod_h.py", body)

    dead = detect.find_dead_apis(
        src_dirs=[tmp_path / "src"],
        test_dirs=[tmp_path / "tests"],
        allowlist=set(),
    )
    names = [d.symbol.name for d in dead]
    assert "SelfReferenced" not in names


def test_devolaflow_codebase_has_no_dead_apis() -> None:
    """THE BIG ONE: real ``src/devolaflow/`` must have no dead public APIs.

    Modulo the documented allowlist in ``scripts/detect_dead_apis.py``.
    Failure here means a new public symbol was added without wiring it
    into a production caller — the v6.0.3 dead-wire bug class.

    To resolve a failure you have three options (per task spec):

    1. **Wire the symbol** into a real caller — usually the right fix
       when the symbol was added to be invoked by a sibling module.
    2. **Mark the symbol private** (rename with ``_`` prefix) — when it
       was never meant to be public.
    3. **Add it to ``DEFAULT_ALLOWLIST``** with a comment explaining
       why it is intentionally external-only.

    The current allowlist documents the v6.1.3 baseline of intentional
    external-only public APIs (adapter base, registry factories,
    MIGRATION-v6.md replacements, NineS subsystem, pre-decision API,
    template engine API, feedback module, gate reporters, learnings
    utilities, compressor validators).
    """
    src_dirs = [REPO_ROOT / "src"]
    test_dirs = [REPO_ROOT / "tests"]
    other_dirs = [REPO_ROOT / "scripts", REPO_ROOT / "benchmarks"]

    dead = detect.find_dead_apis(
        src_dirs=src_dirs,
        test_dirs=test_dirs,
        other_caller_dirs=other_dirs,
        allowlist=detect.DEFAULT_ALLOWLIST,
    )

    if dead:
        listing = "\n".join(
            f"  - {d.symbol.qualified} (in {d.symbol.file.relative_to(REPO_ROOT)})" for d in dead
        )
        pytest.fail(
            f"Detected {len(dead)} dead public API(s) — likely v6.0.3-style dead-wire bugs:\n"
            f"{listing}\n"
            "Wire them, mark private, or allowlist with comment."
        )


def test_dead_api_script_exits_strict(tmp_path: Path) -> None:
    """``detect_dead_apis.py --strict`` exits with code 2 on a dead-API tree."""
    _write_src(tmp_path, "mod_strict.py", "def dangling():\n    return 0\n")

    fake_root = tmp_path / "fake_root"
    fake_root.mkdir()
    (fake_root / "src").symlink_to(tmp_path / "src")
    (fake_root / "tests").mkdir()
    (fake_root / "scripts").mkdir()
    (fake_root / "pyproject.toml").write_text('[project]\nname = "fake"\n')

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--strict",
            "--root",
            str(fake_root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2, (
        f"strict mode should exit 2 on dead APIs, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "dangling" in result.stdout


def test_default_allowlist_no_ssot_overlap() -> None:
    """A-5: ``DEFAULT_ALLOWLIST`` must not contain any domain-SSOT registry symbol.

    Per Architecture Rule A-5.2 (``.rules/architecture.mdc``), every
    qualified name in :data:`scripts.detect_dead_apis.SSOT_REGISTRY_QUALIFIED_NAMES`
    has in-repo production callers in its owner module's siblings, so it
    cannot be allowlisted as "no production caller". The script-import-time
    guard would already have raised :class:`AssertionError` before this
    test runs; this test pins the contract explicitly so a clear failure
    message surfaces if the import-time check is ever weakened.
    """
    overlap = detect._check_allowlist_domain_overlap(detect.DEFAULT_ALLOWLIST)
    assert overlap == set(), (
        f"A-5 violation: DEFAULT_ALLOWLIST contains domain-SSOT registry "
        f"symbol(s) {sorted(overlap)}; per .rules/architecture.mdc::A-5.2, "
        f"remove them and route consumers through the owner module."
    )


def test_check_allowlist_domain_overlap_helper_detects_collisions() -> None:
    """A-5: helper returns the intersection of allowlist with registry names.

    Verifies the helper's behaviour against synthetic fixtures (the live
    DEFAULT_ALLOWLIST is exercised by
    :func:`test_default_allowlist_no_ssot_overlap`). The helper must:

    * Return a non-empty set whose members are exactly the colliding names.
    * Return an empty set when no collision exists.
    * Default ``registry_names`` to :data:`SSOT_REGISTRY_QUALIFIED_NAMES`
      so callers in the rest of the codebase can call it positionally.
    """
    fake_allowlist = {
        "devolaflow.shell_proxy.registry:WHITELIST",
        "devolaflow.harmless:public_helper",
    }
    fake_registries = {"devolaflow.shell_proxy.registry:WHITELIST"}
    assert detect._check_allowlist_domain_overlap(fake_allowlist, fake_registries) == {
        "devolaflow.shell_proxy.registry:WHITELIST"
    }

    assert (
        detect._check_allowlist_domain_overlap({"devolaflow.harmless:x"}, fake_registries) == set()
    )

    # Default registry_names argument resolves to SSOT_REGISTRY_QUALIFIED_NAMES.
    assert detect._check_allowlist_domain_overlap(
        {"devolaflow.shell_proxy.registry:WHITELIST"}
    ) == {"devolaflow.shell_proxy.registry:WHITELIST"}


def test_dead_api_json_output_valid(tmp_path: Path) -> None:
    """``--format json`` produces a valid JSON document with the expected schema."""
    _write_src(tmp_path, "mod_json.py", "def jdangling():\n    return 0\n")

    fake_root = tmp_path / "fake_root"
    fake_root.mkdir()
    (fake_root / "src").symlink_to(tmp_path / "src")
    (fake_root / "tests").mkdir()
    (fake_root / "scripts").mkdir()
    (fake_root / "pyproject.toml").write_text('[project]\nname = "fake"\n')

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--format",
            "json",
            "--root",
            str(fake_root),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "dead_count" in payload
    assert "dead" in payload
    assert payload["dead_count"] >= 1
    assert any(item["symbol"]["name"] == "jdangling" for item in payload["dead"])
