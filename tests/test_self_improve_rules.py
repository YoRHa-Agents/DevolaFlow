"""Tests for the canonical surfaces that absorbed the SI-1..SI-10 rules.

v14.2.1 (G-008) retargeting note: this file originally pinned
``.cursor/rules/self-improve-iteration-rules.mdc``, the always-applied
legacy carrier of the SI-1..SI-10 self-improve iteration rules. That
file is now a deprecated ≤ 50-line pointer stub (v14.2.0 gap register
§2.2 G-008); the rule CONTENT lives in the canonical ``.rules/``
corpus. Every assertion below is the retargeted form of its pre-v14.2.1
ancestor (1:1 function conversion — no test was dropped), pointed at
the canonical carrier per the SI → canonical mapping:

| Legacy | Canonical | Carrier |
|--------|-----------|---------|
| SI-1   | W-1       | ``.rules/workflow.mdc`` |
| SI-2   | W-2       | ``.rules/workflow.mdc`` (NineS analyze + self-eval invocations) |
| SI-3   | W-3       | ``.rules/workflow.mdc`` |
| SI-4   | W-4       | ``.rules/workflow.mdc`` (EvoBench regression guard) |
| SI-5   | W-5       | ``.rules/workflow.mdc`` |
| SI-6   | W-6       | ``.rules/workflow.mdc`` (token-budget table also at A-3) |
| SI-7   | S-7       | ``.rules/soul.mdc`` (generic external-URL policy) |
| SI-8   | W-7       | ``.rules/workflow.mdc`` |
| SI-9   | W-8       | ``.rules/workflow.mdc`` (reinforcement module path) |
| SI-10  | W-9       | ``.rules/workflow.mdc`` |

The explicit canonical URLs the legacy SI-7 enumerated now live at
machine-readable carriers: NineS at
``workflow-system/agent/knowledge/runtime-plugins.yaml`` (the A-5 SSOT
runtime plugin registry, ``canonical_url`` field) and DevolaFlow /
EvoBench at ``benchmarks/devolaflow_context/__init__.py`` (the
benchmark suite's own repository pointer).

Complementary lints (NOT duplicated here): the stub's fingerprint +
≤ 50-line ceiling are pinned by
``tests/test_no_ghost_features.py::test_rule_surfaces_compile_only``;
per-layer rule counts vs ``.rules/index.md`` are pinned by the G-034
parity assertion inside ``test_rule_count_under_cap``.
"""

import re
from pathlib import Path

import pytest

WORKFLOW_REL_PATH = ".rules/workflow.mdc"
SOUL_REL_PATH = ".rules/soul.mdc"
STUB_REL_PATH = ".cursor/rules/self-improve-iteration-rules.mdc"
RUNTIME_PLUGINS_REL_PATH = "workflow-system/agent/knowledge/runtime-plugins.yaml"
EVOBENCH_INIT_REL_PATH = "benchmarks/devolaflow_context/__init__.py"

# SI rule id → (canonical rule id, carrier rel-path). SI-7 landed at the
# Soul layer (external-URL policy); the other nine landed at Workflow.
SI_TO_CANONICAL: dict[str, tuple[str, str]] = {
    "SI-1": ("W-1", WORKFLOW_REL_PATH),
    "SI-2": ("W-2", WORKFLOW_REL_PATH),
    "SI-3": ("W-3", WORKFLOW_REL_PATH),
    "SI-4": ("W-4", WORKFLOW_REL_PATH),
    "SI-5": ("W-5", WORKFLOW_REL_PATH),
    "SI-6": ("W-6", WORKFLOW_REL_PATH),
    "SI-7": ("S-7", SOUL_REL_PATH),
    "SI-8": ("W-7", WORKFLOW_REL_PATH),
    "SI-9": ("W-8", WORKFLOW_REL_PATH),
    "SI-10": ("W-9", WORKFLOW_REL_PATH),
}

ABS_PATH_PATTERN = re.compile(r"(?<!\w)(/(?:home|Users|tmp|var|opt|usr|etc|benchmarks)/\S+)")

# The three rule surfaces the S-2/SF-5 relative-paths contract is
# asserted against here: both canonical carriers + the pointer stub.
RULE_SURFACE_REL_PATHS = (WORKFLOW_REL_PATH, SOUL_REL_PATH, STUB_REL_PATH)


@pytest.fixture
def workflow_content(project_root: Path) -> str:
    return (project_root / WORKFLOW_REL_PATH).read_text(encoding="utf-8")


@pytest.fixture
def soul_content(project_root: Path) -> str:
    return (project_root / SOUL_REL_PATH).read_text(encoding="utf-8")


@pytest.fixture
def stub_content(project_root: Path) -> str:
    return (project_root / STUB_REL_PATH).read_text(encoding="utf-8")


class TestFileExists:
    def test_mdc_file_exists(self, project_root: Path):
        """Canonical carriers exist AND the legacy path still points at them."""
        for rel in (WORKFLOW_REL_PATH, SOUL_REL_PATH):
            assert (project_root / rel).is_file(), f"canonical carrier missing: {rel}"
        stub = project_root / STUB_REL_PATH
        assert stub.is_file(), (
            f"{STUB_REL_PATH} must remain on disk as a deprecated pointer stub "
            f"(G-008) so legacy auto-load paths still surface the cross-reference"
        )
        stub_text = stub.read_text(encoding="utf-8")
        assert "Deprecated" in stub_text and WORKFLOW_REL_PATH in stub_text, (
            f"{STUB_REL_PATH} must point at the canonical {WORKFLOW_REL_PATH} source"
        )


class TestFrontmatter:
    def test_has_yaml_frontmatter(self, workflow_content: str, soul_content: str):
        for name, content in (("workflow", workflow_content), ("soul", soul_content)):
            assert content.startswith("---"), f".rules/{name}.mdc must start with frontmatter"
            parts = content.split("---", 2)
            assert len(parts) >= 3, f".rules/{name}.mdc must have opening/closing --- delimiters"

    def test_always_apply_true(self, soul_content: str, workflow_content: str, stub_content: str):
        """Layer semantics: Soul is always-applied; Workflow is on-demand.

        The legacy file asserted ``alwaysApply: true`` on the SI carrier.
        Post-G-008 the always-on guarantee is carried by the Soul layer +
        the compiled ``repo-governance.mdc`` target; the pointer stub
        keeps ``alwaysApply: true`` so every session still surfaces the
        cross-reference. The Workflow layer is deliberately
        ``alwaysApply: false`` (loaded via the compiled corpus).
        """
        soul_fm = soul_content.split("---", 2)[1]
        assert "alwaysApply: true" in soul_fm or "alwaysApply: True" in soul_fm
        stub_fm = stub_content.split("---", 2)[1]
        assert "alwaysApply: true" in stub_fm or "alwaysApply: True" in stub_fm
        workflow_fm = workflow_content.split("---", 2)[1]
        assert "alwaysApply: false" in workflow_fm or "alwaysApply: False" in workflow_fm

    def test_has_description(self, workflow_content: str, soul_content: str):
        for name, content in (("workflow", workflow_content), ("soul", soul_content)):
            frontmatter = content.split("---", 2)[1]
            assert "description:" in frontmatter, f".rules/{name}.mdc missing description"


class TestRuleSections:
    @pytest.mark.parametrize(("si_id", "canonical"), sorted(SI_TO_CANONICAL.items()))
    def test_rule_section_present(self, project_root: Path, si_id: str, canonical: tuple[str, str]):
        """Each former SI rule has a canonical heading AND a traceable SI tag."""
        canon_id, carrier_rel = canonical
        carrier = (project_root / carrier_rel).read_text(encoding="utf-8")
        heading = rf"^## {re.escape(canon_id)} — "
        assert re.search(heading, carrier, re.MULTILINE), (
            f"{si_id} → {canon_id}: missing canonical rule heading in {carrier_rel}"
        )
        assert re.search(rf"\b{re.escape(si_id)}\b", carrier), (
            f"{si_id} → {canon_id}: the SI id must stay traceable in {carrier_rel} "
            f"(heading suffix like '(SI-N)' or a 'Sources:' citation)"
        )

    def test_all_ten_rules_present(self, workflow_content: str, soul_content: str):
        corpus = workflow_content + soul_content
        found = sorted(
            set(re.findall(r"\bSI-(\d+)\b", corpus)),
            key=int,
        )
        assert found == [str(i) for i in range(1, 11)], (
            f"Expected SI-1..SI-10 all traceable in the canonical corpus, found SI-{found}"
        )

    def test_rules_in_order(self, workflow_content: str):
        """The nine Workflow-absorbed SI rules keep W-order AND SI-order."""
        pairs = re.findall(r"^## (W-\d+) — .+\((SI-\d+)\)\s*$", workflow_content, re.MULTILINE)
        expected = [
            ("W-1", "SI-1"),
            ("W-2", "SI-2"),
            ("W-3", "SI-3"),
            ("W-4", "SI-4"),
            ("W-5", "SI-5"),
            ("W-6", "SI-6"),
            ("W-7", "SI-8"),
            ("W-8", "SI-9"),
            ("W-9", "SI-10"),
        ]
        assert pairs == expected, f"SI-tagged Workflow rules out of order/mapping: {pairs}"


class TestNoAbsolutePaths:
    @pytest.mark.parametrize("rel_path", RULE_SURFACE_REL_PATHS)
    def test_no_absolute_filesystem_paths(self, project_root: Path, rel_path: str):
        content = (project_root / rel_path).read_text(encoding="utf-8")
        matches = ABS_PATH_PATTERN.findall(content)
        assert not matches, (
            f"{rel_path}: absolute filesystem paths found "
            f"(use relative paths or GitHub URLs per S-2/S-7): {matches}"
        )

    @pytest.mark.parametrize("rel_path", RULE_SURFACE_REL_PATHS)
    def test_no_home_paths(self, project_root: Path, rel_path: str):
        content = (project_root / rel_path).read_text(encoding="utf-8")
        assert "/home/" not in content, f"{rel_path} contains /home/ absolute path"

    @pytest.mark.parametrize("rel_path", RULE_SURFACE_REL_PATHS)
    def test_no_users_paths(self, project_root: Path, rel_path: str):
        content = (project_root / rel_path).read_text(encoding="utf-8")
        assert "/Users/" not in content, f"{rel_path} contains /Users/ absolute path"


class TestContentQuality:
    def test_references_github_urls(self, project_root: Path, soul_content: str):
        """S-7 carries the URL policy; explicit URLs live at SSOT carriers.

        The legacy SI-7 enumerated the two canonical URLs inline. The
        compiled S-7 keeps the policy generic; the explicit URLs survive
        at machine-readable carriers — NineS at the A-5 runtime-plugin
        registry's ``canonical_url`` field, DevolaFlow/EvoBench at the
        benchmark suite's own repository pointer.
        """
        assert "remote GitHub URL" in soul_content, "S-7 must state the external-URL policy"
        assert "MUST NOT be hardcoded" in soul_content, (
            "S-7 must forbid hardcoded local clone paths"
        )
        runtime_plugins = (project_root / RUNTIME_PLUGINS_REL_PATH).read_text(encoding="utf-8")
        assert "https://github.com/YoRHa-Agents/NineS" in runtime_plugins, (
            f"NineS canonical URL missing from {RUNTIME_PLUGINS_REL_PATH} "
            f"(the A-5 SSOT runtime plugin registry)"
        )
        evobench_init = (project_root / EVOBENCH_INIT_REL_PATH).read_text(encoding="utf-8")
        assert "https://github.com/YoRHa-Agents/DevolaFlow" in evobench_init, (
            f"DevolaFlow/EvoBench canonical URL missing from {EVOBENCH_INIT_REL_PATH}"
        )

    def test_references_evobench(self, workflow_content: str):
        assert "test_benchmarks.py" in workflow_content, (
            "W-4 (ex-SI-4) must cite the EvoBench verification suite"
        )

    def test_references_reinforcement(self, workflow_content: str):
        assert "src/devolaflow/gate/reinforcement.py" in workflow_content, (
            "W-8 (ex-SI-9) must cite the reinforcement mechanism module path"
        )

    def test_references_nines(self, workflow_content: str):
        assert "nines -f json" in workflow_content, (
            "W-2 (ex-SI-2) must carry the canonical NineS invocation"
        )
        assert "self-eval" in workflow_content, (
            "W-2 (ex-SI-2) must carry the NineS self-eval invocation"
        )
