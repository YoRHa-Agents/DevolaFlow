"""Regression guards for v21.3.0 T5 silent-exception cleanup."""

from __future__ import annotations

import ast
import io
import sys
from pathlib import Path

import pytest

_COVERED_MODULES = (
    "src/devolaflow/learnings.py",
    "src/devolaflow/agent_workspace/change.py",
    "src/devolaflow/template_engine/runtime.py",
    "src/devolaflow/agent_workspace/checkpoint.py",
    "src/devolaflow/local/archive_kernel.py",
    "src/devolaflow/hostbridge/__main__.py",
    "src/devolaflow/task_adaptive_selector.py",
    "src/devolaflow/_compressor_transforms/retrieval.py",
)

# These are sentinel probes, not swallowed failures:
# numeric coercion probes, bounded random-name collision retry, and a
# worktree containment test where ValueError means "not contained".
_INTENTIONAL_SILENT_HANDLERS = [
    (
        "src/devolaflow/agent_workspace/checkpoint.py",
        "_replace_latest",
        "FileExistsError",
        "Continue",
    ),
    ("src/devolaflow/template_engine/runtime.py", "_coerce_bare_rhs", "ValueError", "Pass"),
    ("src/devolaflow/template_engine/runtime.py", "_coerce_bare_rhs", "ValueError", "Pass"),
    ("src/devolaflow/local/archive_kernel.py", "inspect_safety", "ValueError", "Continue"),
]


def _silent_handlers(path: Path, relative: str) -> list[tuple[str, str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, str, str, str]] = []
    function_stack: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            function_stack.append(node.name)
            self.generic_visit(node)
            function_stack.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # noqa: N815

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.body and all(isinstance(stmt, (ast.Pass, ast.Continue)) for stmt in node.body):
                found.append(
                    (
                        relative,
                        function_stack[-1] if function_stack else "<module>",
                        ast.unparse(node.type) if node.type else "bare",
                        type(node.body[0]).__name__,
                    )
                )
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def test_covered_modules_have_only_documented_silent_handlers(project_root: Path) -> None:
    """New pass/continue exception handlers fail the current-cycle ghost audit."""
    actual = sorted(
        handler
        for relative in _COVERED_MODULES
        for handler in _silent_handlers(project_root / relative, relative)
    )
    assert actual == sorted(_INTENTIONAL_SILENT_HANDLERS)


def test_hostbridge_cli_logs_unexpected_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The fail-open protocol remains compatible while unexpected errors are visible."""
    from devolaflow.hostbridge import __main__ as hostbridge_main

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("synthetic bridge failure")

    monkeypatch.setattr(hostbridge_main, "normalize_event", boom)
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    with caplog.at_level("WARNING", logger="devolaflow.hostbridge.__main__"):
        assert hostbridge_main.main(["--host", "cursor"]) == 0
    record = next(record for record in caplog.records if "internal error" in record.message)
    assert record.exc_info is not None


def test_selector_logs_tiktoken_degradation(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An unexpected tokenizer failure uses the deterministic fallback with context."""
    import devolaflow.task_adaptive_selector as selector

    monkeypatch.setitem(sys.modules, "tiktoken", object())
    monkeypatch.setattr(
        selector,
        "_estimate_tokens_tiktoken_cached",
        lambda text: (_ for _ in ()).throw(RuntimeError("synthetic tokenizer failure")),
    )
    with caplog.at_level("WARNING", logger="devolaflow.task_adaptive_selector"):
        assert selector.estimate_tokens("fallback test") == len("fallback test") // 4
    record = next(record for record in caplog.records if "estimator failed" in record.message)
    assert record.exc_info is not None


def test_retrieval_parser_logs_degraded_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Parser errors remain nonblocking but identify the markdown fallback."""
    import yaml

    from devolaflow._compressor_transforms import retrieval

    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("synthetic YAML parser failure")

    monkeypatch.setattr(yaml, "safe_load", boom)
    with caplog.at_level("WARNING", logger="devolaflow._compressor_transforms.retrieval"):
        sections = retrieval._parse_yaml_sections("## Heading\nbody")
    assert sections == [("Heading", "body")]
    record = next(record for record in caplog.records if "YAML parsing failed" in record.message)
    assert record.exc_info is not None


def test_learning_timestamp_recovery_logs(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed timestamps retain the documented nonblocking behavior visibly."""
    import json

    from devolaflow.learnings import get_learnings_stats, prune_learnings

    path = tmp_path / "operational.jsonl"
    entry = {
        "stage": "test",
        "task_type": "feature",
        "key": "bad-timestamp",
        "insight": "keep this record",
        "confidence": 0.8,
        "timestamp": "not-a-timestamp",
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    with caplog.at_level("WARNING", logger="devolaflow.learnings"):
        assert prune_learnings(path) == 0
        assert get_learnings_stats(path)["expired_count"] == 0
    assert sum("malformed" in record.message.lower() for record in caplog.records) == 2
    assert all(record.exc_info is not None for record in caplog.records)
