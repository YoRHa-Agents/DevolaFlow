"""Semantic alignment checks for release, generated data, and Pages workflows."""

from __future__ import annotations

import json
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
        "group": "release-${{ inputs.release_tag || github.ref_name }}",
        "cancel-in-progress": False,
    }
    assert workflow["permissions"] == {}

    jobs = workflow["jobs"]
    verify = jobs["verify-release-ref"]
    assert verify["permissions"] == {"contents": "read"}
    assert verify["steps"][0] == {
        "uses": "actions/checkout@v7",
        "with": {"fetch-depth": 0, "ref": "${{ inputs.release_sha || github.sha }}"},
    }
    assert _run_step_index(
        verify,
        "git fetch --no-tags origin main:refs/remotes/origin/main",
    ) < _run_step_index(
        verify,
        'git merge-base --is-ancestor "$RELEASE_SHA" origin/main',
    )
    assert jobs["checks"] == {
        "needs": "verify-release-ref",
        "permissions": {"contents": "read"},
        "uses": "./.github/workflows/ci-checks.yml",
        "with": {
            "checkout_ref": "${{ inputs.release_sha || github.sha }}",
            "expected_sha": "${{ inputs.release_sha || github.sha }}",
        },
    }
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
    assert steps[0]["with"]["ref"] == "${{ inputs.release_sha || github.sha }}"
    build_index = _run_step_index(deploy, "bash scripts/build-site.sh")
    assert build_index > 0
    assert steps[build_index + 1] == {
        "uses": "actions/upload-pages-artifact@v5",
        "with": {"path": "_site"},
    }
    assert steps[build_index + 2] == {"uses": "actions/deploy-pages@v5", "id": "deployment"}

    npm = _load_workflow("npm-publish.yml")
    assert _triggers(npm)["push"]["tags"] == ["v*"]
    assert npm["concurrency"] == {
        "group": "npm-publish-${{ inputs.release_tag || github.ref_name }}",
        "cancel-in-progress": False,
    }
    assert npm["permissions"] == {}
    npm_jobs = npm["jobs"]
    assert npm_jobs["checks"] == {
        "permissions": {"contents": "read"},
        "uses": "./.github/workflows/ci-checks.yml",
        "with": {
            "checkout_ref": "${{ inputs.release_sha || github.sha }}",
            "expected_sha": "${{ inputs.release_sha || github.sha }}",
        },
    }
    publish = npm_jobs["publish"]
    assert publish["needs"] == "checks"
    assert publish["permissions"] == {
        "contents": "read",
        "id-token": "write",
    }
    assert publish["steps"][0] == {
        "uses": "actions/checkout@v7",
        "with": {"fetch-depth": 0, "ref": "${{ inputs.release_sha || github.sha }}"},
    }
    reachability = _run_step_index(
        publish,
        'git merge-base --is-ancestor "$RELEASE_SHA" origin/main',
    )
    parity = _run_step_index(publish, 'TAG_VERSION="${RELEASE_TAG#v}"')
    publication = _run_step_index(publish, "npm publish --provenance --access public")
    assert reachability < parity < publication


def test_release_automation_is_guarded_and_reusable() -> None:
    prep = _load_workflow("release-prep.yml")
    prep_triggers = _triggers(prep)
    version_input = prep_triggers["workflow_dispatch"]["inputs"]["version"]
    assert version_input["required"] is True
    assert version_input["type"] == "string"
    assert prep["permissions"] == {}
    prep_job = prep["jobs"]["prepare"]
    assert prep_job["permissions"] == {"contents": "write", "pull-requests": "write"}
    prep_steps = json.dumps(prep_job["steps"])
    for command in (
        "python scripts/bump_version.py",
        "make sync-human-docs",
        "make release-preflight",
        "Validate existing CHANGELOG entry",
        "gh pr create",
    ):
        assert command in prep_steps
    assert "git clean" not in prep_steps
    assert "CHANGELOG.md" in prep_steps


def test_release_pr_creation_falls_back_to_manual_command_without_token() -> None:
    prep = _load_workflow("release-prep.yml")
    open_pr = next(
        step for step in prep["jobs"]["prepare"]["steps"] if step.get("name") == "Open release PR"
    )
    run = open_pr["run"]

    assert "if gh pr create \\" in run
    assert "then" in run
    assert "::warning::GitHub Actions could not create the release PR" in run
    assert "Branch URL: https://github.com/$GITHUB_REPOSITORY/tree/$branch_name" in run
    assert "Manual command: gh pr create" in run
    assert "GITHUB_TOKEN" not in run
    assert "exit 1" not in run[run.index("if gh pr create") :]


def test_current_demo_release_window_has_no_upcoming_release_residue(project_root: Path) -> None:
    demo = (project_root / "workflow-system/human/demo/index.html").read_text(encoding="utf-8")

    assert "Upcoming release" not in demo
    assert "即将发布" not in demo
    assert demo.count("New in v22.0.0 · Optional Tool Retirement") == 2
    assert "v22.0.0 新变化 · Optional Tool Retirement" in demo


def test_demo_promotion_allows_already_promoted_pages() -> None:
    prep = _load_workflow("release-prep.yml")
    promote = next(
        step
        for step in prep["jobs"]["prepare"]["steps"]
        if step.get("name") == "Promote prepared demo release window"
    )
    run = promote["run"]

    assert r"home\.release\.v19\.heading" in run
    assert "if updated == text:" in run
    assert "::warning::demo/index.html has no release-window placeholder" in run
    assert "Continuing." in run
    assert "raise SystemExit" not in run

    auto_tag = _load_workflow("auto-tag-release.yml")
    auto_triggers = _triggers(auto_tag)
    assert auto_triggers["push"] == {
        "branches": ["main"],
        "paths": ["src/devolaflow/__init__.py"],
    }
    assert auto_tag["permissions"] == {}
    tag_job = auto_tag["jobs"]["create-tag"]
    assert tag_job["permissions"] == {"contents": "write"}
    tag_steps = json.dumps(tag_job["steps"])
    assert "git ls-remote --exit-code --refs origin" in tag_steps
    assert "git tag --annotate" in tag_steps
    assert "git push origin" in tag_steps
    assert "git clean" not in tag_steps
    assert auto_tag["jobs"]["release"]["uses"] == "./.github/workflows/release.yml"
    assert auto_tag["jobs"]["npm-publish"]["uses"] == "./.github/workflows/npm-publish.yml"
    assert auto_tag["jobs"]["npm-publish"]["secrets"] == "inherit"

    for workflow_name in ("release.yml", "npm-publish.yml"):
        triggers = _triggers(_load_workflow(workflow_name))
        inputs = triggers["workflow_call"]["inputs"]
        assert set(inputs) == {"release_tag", "release_sha"}
        assert all(input_spec["required"] is True for input_spec in inputs.values())


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
    ]
    release_only = [
        "validate-templates",
        "check-template-metadata-parity",
        "build-skill",
        "sync-human-docs",
        "compile-rules",
        "check-drift",
        "check-rules-drift",
    ]
    first_release_only = min(dependencies.index(item) for item in release_only)
    assert all(dependencies.index(item) < first_release_only for item in core)
    assert dependencies.index("sync-human-docs") < dependencies.index("compile-rules")
    assert (
        dependencies.index("validate-templates")
        < dependencies.index("check-template-metadata-parity")
        < dependencies.index("build-skill")
    )

    assert _target_recipe(makefile, "check-template-metadata-parity") == [
        (
            "@$(call RUN_TIMED,check-template-metadata-parity,python "
            "scripts/check_template_metadata_parity.py)"
        )
    ]

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


def test_release_preflight_runs_full_ghosts_and_dry_run_uses_same_contract() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    dependencies = _target_line(makefile, "release-preflight").split(":", 1)[1].split()
    assert "check-repo-hygiene" in dependencies
    assert all(
        target not in dependencies
        for target in (
            "ghost-full",
            "check-functional-matrix",
            "check-agent-language",
            "check-import-graph",
            "check-module-size",
        )
    )

    ghost_recipe = _target_recipe(makefile, "ghost-full")
    assert ghost_recipe == [
        "@$(call RUN_TIMED,ghost-full,GHOST_FULL=1 python -m pytest tests/ghost/ -v --tb=short)"
    ]
    hygiene_recipe = _target_recipe(makefile, "check-repo-hygiene")
    assert hygiene_recipe == [
        (
            "@$(call RUN_TIMED,check-repo-hygiene,python "
            "scripts/check_repo_hygiene.py --root . --baseline-ref origin/main)"
        )
    ]
    hygiene_source = (ROOT / "scripts" / "check_repo_hygiene.py").read_text(encoding="utf-8")
    for check_name in (
        "agent-language",
        "import-graph",
        "module-size",
        "functional-matrix",
        "ghost",
    ):
        assert f'"{check_name}"' in hygiene_source

    dry_run_recipe = _target_recipe(makefile, "release-dry-run")
    assert "$(MAKE) release-preflight" in dry_run_recipe
    assert not any("$(MAKE) lint" in line for line in dry_run_recipe)
    assert not any("$(MAKE) build-site" in line for line in dry_run_recipe)


def test_shared_ci_enforces_module_size_and_complete_coverage() -> None:
    workflow = _load_workflow("ci-checks.yml")
    assert _triggers(workflow)["workflow_call"]["inputs"] == {
        "checkout_ref": {
            "description": "Exact ref or SHA to check out",
            "required": False,
            "default": "",
            "type": "string",
        },
        "expected_sha": {
            "description": "When set, the checkout must resolve to this full SHA",
            "required": False,
            "default": "",
            "type": "string",
        },
    }
    check_steps = workflow["jobs"]["check"]["steps"]
    module_size = next(step for step in check_steps if step.get("name") == "Module size budget")
    assert (
        "git fetch --no-tags --depth=1 origin main:refs/remotes/origin/main" in module_size["run"]
    )
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
    assert 'git merge-base --is-ancestor "$RELEASE_SHA" origin/main' in design
    assert "npm-publish.yml" in design
    assert "`publish`" in design
    assert "repository-wide `pages`" in design

    obsolete_claims = ("all 16 version locations", "all 10 version locations", "sample_data")
    lowered = design.lower()
    assert not any(claim in lowered for claim in obsolete_claims)
