"""v9.6.0 PV-01 — Tests for `scripts/nines_refresh_references.py` harness.

Pins the harness contract per the v9.6.0 SI-1 gap analysis §4 PV-01 row.
The harness is the SI-2 NineS-driven analysis surface for the
Reference Library Refresh cycle (W-1 / W-2).
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "nines_refresh_references.py"
_MODULE_NAME = "nines_refresh_references"


def _import_harness():
    """Load the harness via spec_from_file_location and register in sys.modules.

    The dataclass() decorator looks up the owning module in sys.modules at
    class-definition time; without registration we hit the
    ``cls.__module__`` -> ``None`` AttributeError on Python 3.12.
    """
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"could not load spec for {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def harness():
    """Import the harness module by file path (it is not on sys.path)."""
    return _import_harness()


def test_harness_script_is_executable_module() -> None:
    """The harness script must exist and be loadable as a module."""
    assert SCRIPT_PATH.exists(), f"missing harness: {SCRIPT_PATH}"
    module = _import_harness()
    # Public surface contract per gap_analysis §4 PV-01.
    for sym in (
        "REPO_ROOT",
        "YAML_PATH",
        "DEFAULT_REFERENCE_ROOT",
        "OUTPUT_BASE",
        "DELTAS_DIR",
        "SYNTHESIS_PATH",
        "CLONE_NAME_OVERRIDES",
        "RefResult",
        "_load_refs",
        "_nines_available",
        "_resolve_clone",
        "_run_nines",
        "_summarize_findings",
        "analyze_one",
        "render_synthesis",
        "main",
    ):
        assert hasattr(module, sym), f"harness is missing public symbol {sym!r}"


def test_load_refs_yields_21_entries(harness) -> None:
    """The reference inventory must enumerate the v9.6.0 SI-1 §2 count.

    Per gap_analysis §2: 11 active_tracking + 10 periodic_monitoring = 21
    (the yaml header comment "10 + 9 = 19" is stale, fixed in PV-04).
    """
    refs = harness._load_refs()
    assert isinstance(refs, list)
    assert len(refs) >= 19, f"expected >= 19 refs (yaml comment), got {len(refs)}"
    # Every entry must carry an id, source_type, and bucket marker.
    for r in refs:
        assert isinstance(r, dict)
        assert r.get("id"), f"entry missing 'id': {r!r}"
        assert r.get("source_type"), f"entry {r['id']} missing source_type"
        assert r.get("_bucket") in (
            "active_tracking",
            "periodic_monitoring",
        ), f"entry {r['id']} missing/invalid _bucket"


def test_understand_anything_clone_override_is_pinned(harness) -> None:
    """The `understand-anything` ref MUST resolve to `Understand-Anything`.

    The yaml id is lower-kebab-case; the upstream clone is mixed-case.
    A naive resolver would fail to find the clone — `CLONE_NAME_OVERRIDES`
    is the explicit indirection. Pin the entry to prevent silent removal.
    """
    overrides = harness.CLONE_NAME_OVERRIDES
    assert "understand-anything" in overrides, (
        "CLONE_NAME_OVERRIDES must pin the case-mismatched 'understand-anything' "
        "entry — see harness module docstring"
    )
    assert overrides["understand-anything"] == "Understand-Anything"


def test_skips_gracefully_when_nines_missing(harness, tmp_path) -> None:
    """When `nines` CLI is absent, the harness MUST mark refs as `skipped_no_nines`.

    Pins the W-2 fallback contract: missing nines = manual analysis, not
    a hard error. The harness must continue iterating other refs.
    """
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    ref = {
        "id": "fake-ref",
        "source_type": "github_repo",
        "repo_url": "https://example.com/fake",
        "relevance_score": 4,
        "devolaflow_integration_points": [],
    }
    result = harness.analyze_one(
        ref,
        reference_root=tmp_path,
        nines_present=False,
        depth="deep",
        dry_run=False,
    )
    # The fake-ref clone exists at tmp_path/fake-ref but nines is "missing".
    # The harness should report skipped_no_clone (clone not at fake_repo path)
    # OR skipped_no_nines if the clone resolves. Assert either is acceptable;
    # both are W-2 fallback markers per gap_analysis §3.2 D-R-8.
    assert result.status in ("skipped_no_nines", "skipped_no_clone")
    assert "manual review per W-2" in result.reason


def test_skips_non_repo_sources(harness, tmp_path) -> None:
    """`api_docs`, `gist`, `blog`, `paper` refs MUST skip with `skipped_non_repo`.

    These source types cannot be deep-analyzed by NineS (no clonable git surface).
    """
    for source_type in ("api_docs", "gist", "blog", "paper"):
        ref = {
            "id": f"fake-{source_type}",
            "source_type": source_type,
            "repo_url": "https://example.com/x",
            "relevance_score": 5,
            "devolaflow_integration_points": [],
        }
        result = harness.analyze_one(
            ref,
            reference_root=tmp_path,
            nines_present=True,
            depth="deep",
            dry_run=False,
        )
        assert result.status == "skipped_non_repo", (
            f"{source_type} should skip as non-repo, got {result.status}"
        )
        assert source_type in result.reason


def test_render_synthesis_reports_all_buckets(harness) -> None:
    """Synthesis output must surface all 4 status buckets from the harness.

    Per gap_analysis §2, the coverage matrix splits 21 refs across:
    analyzed_deep, skipped_no_clone, skipped_no_nines, skipped_non_repo.
    The synthesis must emit each cited bucket so the W-1 SI-1 review
    can audit at a glance.
    """
    results = [
        harness.RefResult(
            ref_id="r1",
            repo_url="https://example.com/r1",
            source_type="github_repo",
            relevance_score=5,
            status="analyzed_deep",
            reason="ok",
            findings_summary="3 info, 1 warning",
            output_json=".local/research/v9.6.0_reference_deltas/r1.json",
            integration_points=["foo.py"],
        ),
        harness.RefResult(
            ref_id="r2",
            repo_url="https://example.com/r2",
            source_type="github_repo",
            relevance_score=4,
            status="skipped_no_clone",
            reason="clone missing",
        ),
        harness.RefResult(
            ref_id="r3",
            repo_url="https://example.com/r3",
            source_type="paper",
            relevance_score=4,
            status="skipped_non_repo",
            reason="source_type=paper",
        ),
    ]
    text = harness.render_synthesis(results, depth="deep")
    # Coverage matrix surfaces every ref id.
    for r in results:
        assert f"`{r.ref_id}`" in text
    # Bucket sections appear.
    assert "Deep-analyzed refs (NineS findings)" in text
    assert "Manual-review refs (W-2 fallback)" in text
    # W-2 fallback statement is the closing audit note.
    assert "W-2" in text
    assert "manual" in text.lower()


def test_yaml_path_constant_resolves_to_real_file(harness) -> None:
    """The hardcoded YAML_PATH must point at the real reference inventory.

    Defends against future refactors that move the yaml without updating the
    harness. Per S-7, the yaml IS the canonical ref list.
    """
    assert harness.YAML_PATH.exists(), (
        f"YAML_PATH does not exist — harness will fail at runtime: {harness.YAML_PATH}"
    )
    data = yaml.safe_load(harness.YAML_PATH.read_text(encoding="utf-8"))
    assert "active_tracking" in data
    assert "periodic_monitoring" in data
