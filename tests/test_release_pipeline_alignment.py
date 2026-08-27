"""Semantic alignment checks for release, generated data, and Pages workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load_workflow(name: str) -> dict[str, Any]:
    workflow = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    assert isinstance(workflow, dict)
    return workflow


def _triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    # PyYAML follows YAML 1.1 and parses a bare `on:` key as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def _run_step_index(job: dict[str, Any], command: str) -> int:
    return next(index for index, step in enumerate(job["steps"]) if command in step.get("run", ""))


def _target_line(makefile: str, target: str) -> str:
    return next(line for line in makefile.splitlines() if line.startswith(f"{target}:"))


def _target_recipe(makefile: str, target: str) -> list[str]:
    lines = makefile.splitlines()
    start = lines.index(_target_line(makefile, target)) + 1
    recipe: list[str] = []
    for line in lines[start:]:
        if line.startswith("\t"):
            recipe.append(line.strip())
        elif line:
            break
    return recipe


def test_tag_release_gates_release_then_deploys_tagged_site() -> None:
    workflow = _load_workflow("release.yml")
    assert _triggers(workflow)["push"]["tags"] == ["v*"]
    assert workflow["concurrency"] == {
        "group": "release-${{ github.ref }}",
        "cancel-in-progress": False,
    }
    assert workflow["permissions"] == {}

    jobs = workflow["jobs"]
    verify = jobs["verify-release-ref"]
    assert verify["permissions"] == {"contents": "read"}
    assert verify["steps"][0] == {
        "uses": "actions/checkout@v7",
        "with": {"fetch-depth": 0},
    }
    assert _run_step_index(
        verify,
        "git fetch --no-tags origin main:refs/remotes/origin/main",
    ) < _run_step_index(
        verify,
        'git merge-base --is-ancestor "$GITHUB_SHA" origin/main',
    )
    assert jobs["checks"]["uses"] == "./.github/workflows/ci-checks.yml"
    assert jobs["checks"]["permissions"] == {"contents": "read"}
    assert jobs["checks"]["needs"] == "verify-release-ref"
    assert jobs["release-extras"]["needs"] == "verify-release-ref"
    assert jobs["release"]["needs"] == ["checks", "release-extras"]
    assert jobs["release"]["permissions"] == {"contents": "write"}

    deploy = jobs["deploy-pages"]
    assert deploy["needs"] == "release"
    assert deploy["permissions"] == {
        "contents": "read",
        "pages": "write",
        "id-token": "write",
    }
    assert deploy["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    assert deploy["environment"] == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }

    steps = deploy["steps"]
    assert steps[0]["uses"] == "actions/checkout@v7"
    assert steps[0]["with"]["ref"] == "${{ github.sha }}"
    assert "bash scripts/build-site.sh" in steps[1]["run"]
    assert steps[2] == {
        "uses": "actions/upload-pages-artifact@v5",
        "with": {"path": "_site"},
    }
    assert steps[3] == {"uses": "actions/deploy-pages@v5", "id": "deployment"}

    npm = _load_workflow("npm-publish.yml")
    assert _triggers(npm)["push"]["tags"] == ["v*"]
    assert npm["permissions"] == {}
    npm_jobs = npm["jobs"]
    assert npm_jobs["checks"] == {
        "permissions": {"contents": "read"},
        "uses": "./.github/workflows/ci-checks.yml",
    }
    publish = npm_jobs["publish"]
    assert publish["needs"] == "checks"
    assert publish["permissions"] == {
        "contents": "read",
        "id-token": "write",
    }
    assert publish["steps"][0] == {
        "uses": "actions/checkout@v7",
        "with": {"fetch-depth": 0},
    }
    reachability = _run_step_index(
        publish,
        'git merge-base --is-ancestor "$GITHUB_SHA" origin/main',
    )
    parity = _run_step_index(publish, 'TAG_VERSION="${GITHUB_REF_NAME#v}"')
    publication = _run_step_index(publish, "npm publish --provenance --access public")
    assert reachability < parity < publication


def test_ci_and_release_verify_generated_outputs_before_site_build() -> None:
    ci_validate = _load_workflow("ci-checks.yml")["jobs"]["validate"]
    release_extras = _load_workflow("release.yml")["jobs"]["release-extras"]

    for job in (ci_validate, release_extras):
        install = _run_step_index(job, 'pip install -e ".[dev]"')
        sync = _run_step_index(job, "make sync-human-docs")
        diff = _run_step_index(
            job,
            "git diff --exit-code -- workflow-system/human/en workflow-system/human/zh",
        )
        catalog = _run_step_index(job, "make check-demo-seed-catalog")
        build = _run_step_index(job, "make build-site")
        assert install < sync < diff < catalog < build


def test_main_pages_deploy_has_complete_inputs_and_shared_concurrency() -> None:
    workflow = _load_workflow("pages.yml")
    push = _triggers(workflow)["push"]
    assert push["branches"] == ["main"]

    required_paths = {
        "scripts/generate_human_docs.py",
        "scripts/generate_demo_seed_catalog.py",
        "workflow-system/agent/templates/registry.yaml",
        "workflow-system/agent/templates/seeds/**",
        "workflow-system/human/demo/**",
        "workflow-system/human/en/**",
        "workflow-system/human/zh/**",
        "docs/designs/**",
        "scripts/build-site.sh",
        ".github/workflows/pages.yml",
        ".github/workflows/release.yml",
    }
    assert required_paths <= set(push["paths"])
    assert workflow["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    assert workflow["permissions"] == {}

    build = workflow["jobs"]["build"]
    deploy = workflow["jobs"]["deploy"]
    assert build["permissions"] == {"contents": "read"}
    assert _run_step_index(build, "bash scripts/build-site.sh") > 0
    assert any(step.get("uses") == "actions/upload-pages-artifact@v5" for step in build["steps"])
    assert deploy["needs"] == "build"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"]["name"] == "github-pages"
    assert deploy["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
    assert deploy["steps"] == [{"uses": "actions/deploy-pages@v5", "id": "deployment"}]


def test_release_preflight_checks_catalog_then_builds_site() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert _target_recipe(makefile, "generate-demo-seed-catalog") == [
        "python scripts/generate_demo_seed_catalog.py"
    ]
    assert _target_recipe(makefile, "check-demo-seed-catalog") == [
        "python scripts/generate_demo_seed_catalog.py --check"
    ]

    dependencies = _target_line(makefile, "release-preflight").split(":", 1)[1].split()
    core = [
        "test-core",
        "lint",
        "test-version",
        "test-harness",
        "check-cursor-skill",
        "iteration-delta-gate",
    ]
    release_only = [
        "validate-templates",
        "build-skill",
        "sync-human-docs",
        "compile-rules",
        "check-drift",
        "check-rules-drift",
    ]
    first_release_only = min(dependencies.index(item) for item in release_only)
    assert all(dependencies.index(item) < first_release_only for item in core)
    assert dependencies.index("sync-human-docs") < dependencies.index("compile-rules")

    recipe = _target_recipe(makefile, "release-preflight")
    catalog = recipe.index("$(MAKE) check-demo-seed-catalog")
    build = recipe.index("$(MAKE) build-site")
    assert catalog < build
    assert recipe[build + 1 :] == [
        '@echo "--- Release preflight PASSED ---"',
        '@echo "Release sequence (start on a feature branch before this target):"',
        '@echo "1. python scripts/bump_version.py <version>"',
        '@echo "2. make release-preflight  # mandatory on the bumped tree"',
        '@echo "3. Commit the verified bump, open a PR, and merge it into main"',
        '@echo "4. git checkout main"',
        '@echo "5. git fetch origin main && git pull --ff-only origin main"',
        '@echo "6. python scripts/bump_version.py <version> --tag --dry-run"',
        '@echo "7. python scripts/bump_version.py <version> --tag  '
        '# clean main HEAD == origin/main"',
        '@echo "8. git push origin v<version>  # push the tag only"',
    ]
    assert "git push origin main" not in makefile
    assert "git push origin HEAD" not in makefile


def test_shared_ci_enforces_module_size_and_complete_coverage() -> None:
    workflow = _load_workflow("ci-checks.yml")
    check_steps = workflow["jobs"]["check"]["steps"]
    module_size = next(step for step in check_steps if step.get("name") == "Module size budget")
    assert "git fetch --no-tags --depth=1 origin main:refs/remotes/origin/main" in module_size["run"]
    assert "python scripts/check_module_size.py --baseline-ref origin/main" in module_size["run"]

    test_steps = workflow["jobs"]["test"]["steps"]
    coverage = next(step for step in test_steps if step.get("name") == "Pytest with coverage")
    assert "--ignore=tests/harness" not in coverage["run"]
    assert not any("make test-harness" in step.get("run", "") for step in test_steps)


def test_release_design_matches_v17_pipeline_contract() -> None:
    design = (ROOT / "docs" / "designs" / "design_release_workflow.md").read_text(encoding="utf-8")
    assert "seven canonical sync locations across eight files" in design
    assert "packages/npm/package.json" in design
    assert "version-timeline/versions.json" in design
    assert "make check-demo-seed-catalog" in design
    assert "make build-site" in design
    assert "`deploy-pages`" in design
    assert "`verify-release-ref`" in design
    assert 'git merge-base --is-ancestor "$GITHUB_SHA" origin/main' in design
    assert "npm-publish.yml" in design
    assert "`publish`" in design
    assert "repository-wide `pages`" in design

    obsolete_claims = ("all 16 version locations", "all 10 version locations", "sample_data")
    lowered = design.lower()
    assert not any(claim in lowered for claim in obsolete_claims)
