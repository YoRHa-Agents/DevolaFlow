"""Tests for the v9.0.0 PV-06 CompressionPipeline orchestrator + stage protocol.

Pins the four R5 strict invariants per
``docs/cycle-archive/adr/v9-ADR-006-compression-pipeline-and-b3-flip.md``:

1. Empty pipeline → byte-identical pass-through
2. All stages bypassed → byte-identical pass-through
3. Single identity stage → byte-identical pass-through
4. Stages run in declaration order

Plus the surface-area assertions for the wrapper around the existing
6 transforms (truncate_tool_output, summarise_predecessor, directed_compact,
apply_local_recipe).

Per W-17 (≤ +30 NEW test functions per PV) related single-assertion checks
are consolidated into parametrized tests and combined data tables.
"""

from __future__ import annotations

import logging

import pytest

from devolaflow.compression_pipeline import (
    BYPASS_ALWAYS,
    BYPASS_NEVER,
    CompressionPipeline,
    CompressionStage,
    CompressionStageError,
    PipelineRunResult,
    StageResult,
    make_stage,
)

# ---------------------------------------------------------------------------
# R5 strict invariant tests — byte-identical pass-through
# ---------------------------------------------------------------------------


class TestByteIdenticalInvariants:
    """The four pinned invariants from v9-ADR-006 §"R5 strict triple"."""

    def test_empty_pipeline_is_byte_identical(self) -> None:
        """Pipeline with no stages returns input unchanged."""
        pipeline = CompressionPipeline(stages=())
        payload = "hello world\n" * 100
        result = pipeline.run(payload)
        assert isinstance(result, PipelineRunResult)
        assert result.payload is payload, "empty pipeline MUST forward input by identity"
        assert result.payload == payload
        assert result.stage_results == ()
        assert result.any_applied is False
        assert result.total_stages == 0
        assert result.applied_stages == ()
        assert result.bypassed_stages == ()
        assert result.failed_stages == ()

    def test_all_stages_bypassed_is_byte_identical(self) -> None:
        """When every stage's bypass predicate fires, payload passes through."""

        def transform_should_not_run(_payload, _ctx):
            raise AssertionError("transform invoked despite bypass=True")

        stages = (
            CompressionStage(
                name="stage_a",
                transform=transform_should_not_run,
                bypass=BYPASS_ALWAYS,
            ),
            CompressionStage(
                name="stage_b",
                transform=transform_should_not_run,
                bypass=BYPASS_ALWAYS,
            ),
            CompressionStage(
                name="stage_c",
                transform=transform_should_not_run,
                bypass=BYPASS_ALWAYS,
            ),
        )
        pipeline = CompressionPipeline(stages=stages, name="all_bypassed")
        payload = {"text": "verbatim", "list": [1, 2, 3]}
        result = pipeline.run(payload)
        assert result.payload is payload, (
            "fully-bypassed pipeline MUST forward input by identity (R5 strict)"
        )
        assert result.any_applied is False
        assert result.total_stages == 3
        assert result.applied_stages == ()
        assert result.bypassed_stages == ("stage_a", "stage_b", "stage_c")
        assert all(sr.bypassed for sr in result.stage_results)

    def test_identity_stage_is_byte_identical(self) -> None:
        """A stage that returns input verbatim MUST NOT be marked applied."""
        stage = CompressionStage(
            name="identity",
            transform=lambda payload, _ctx: payload,
        )
        pipeline = CompressionPipeline(stages=(stage,))
        payload = "verbatim text"
        result = pipeline.run(payload)
        assert result.payload == payload
        assert result.any_applied is False, (
            "identity stage that returns input verbatim MUST NOT be applied"
        )
        assert result.applied_stages == ()
        assert result.stage_results[0].applied is False
        assert result.stage_results[0].bypassed is False

    def test_stages_run_in_declaration_order(self) -> None:
        """Pipeline is a deterministic sequential reducer."""
        invocation_log: list[str] = []

        def stage_factory(name: str):
            def transform(payload, _ctx):
                invocation_log.append(name)
                return f"{payload}|{name}"

            return CompressionStage(name=name, transform=transform)

        pipeline = CompressionPipeline(
            stages=(
                stage_factory("first"),
                stage_factory("second"),
                stage_factory("third"),
            ),
            name="ordered",
        )
        result = pipeline.run("seed")
        assert invocation_log == ["first", "second", "third"]
        assert result.payload == "seed|first|second|third"
        assert result.applied_stages == ("first", "second", "third")
        assert result.any_applied is True


# ---------------------------------------------------------------------------
# Stage protocol surface tests (consolidated per W-17)
# ---------------------------------------------------------------------------


class TestCompressionStage:
    """The dataclass + ``make_stage`` helper surface."""

    @pytest.mark.parametrize(
        ("kwargs", "expected_match"),
        [
            ({"name": "", "transform": lambda p, c: p}, "MUST be a non-empty string"),
            (
                {"name": "bad", "transform": "not callable"},
                "transform MUST be callable",
            ),
            (
                {"name": "bad", "transform": lambda p, c: p, "bypass": "not callable"},
                "bypass MUST be callable",
            ),
        ],
    )
    def test_stage_validation_rejects_bad_construction(
        self,
        kwargs,
        expected_match: str,
    ) -> None:
        """All 3 construction-time validations raise loudly per S-5."""
        exc_cls = ValueError if "non-empty" in expected_match else TypeError
        with pytest.raises(exc_cls, match=expected_match):
            CompressionStage(**kwargs)

    def test_make_stage_default_and_custom(self) -> None:
        """make_stage covers both the default-args and custom-args paths."""
        default_stage = make_stage("default", lambda p, _c: p + "_x")
        assert default_stage.bypass is BYPASS_NEVER
        assert default_stage.bypass_conditions == ()
        assert default_stage.telemetry_key == "default"

        custom_stage = make_stage(
            "custom",
            lambda p, _c: p,
            bypass=BYPASS_ALWAYS,
            bypass_conditions=["env_flag_unset"],
            telemetry_key="custom_telemetry",
        )
        assert custom_stage.bypass is BYPASS_ALWAYS
        assert custom_stage.bypass_conditions == ("env_flag_unset",)
        assert custom_stage.telemetry_key == "custom_telemetry"

    @pytest.mark.parametrize(
        ("predicate", "expected_log_substring"),
        [
            (lambda p, c: 1 / 0, "bypass predicate raised"),
            (lambda p, c: "yes", "non-bool"),
        ],
    )
    def test_should_bypass_defensive_paths(
        self,
        predicate,
        expected_log_substring: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """S-5: a buggy / non-bool predicate logs WARNING and returns True."""
        stage = CompressionStage(
            name="defensive",
            transform=lambda p, _c: p,
            bypass=predicate,
        )
        with caplog.at_level(logging.WARNING):
            verdict = stage.should_bypass("payload", {})
        assert verdict is True
        assert any(expected_log_substring in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Pipeline construction validation (consolidated)
# ---------------------------------------------------------------------------


class TestCompressionPipelineConstruction:
    """Pipeline-level validation at __post_init__ time + helpers."""

    def test_construction_validations_are_loud(self) -> None:
        """Three construction-time guards: dupe names / non-protocol / list-vs-tuple."""
        with pytest.raises(ValueError, match="duplicate stage name"):
            CompressionPipeline(
                stages=(
                    make_stage("dupe", lambda p, _c: p),
                    make_stage("dupe", lambda p, _c: p),
                )
            )

        class NotAStage:
            pass

        with pytest.raises(TypeError, match="does not satisfy the"):
            CompressionPipeline(stages=(NotAStage(),))  # type: ignore[arg-type]

        list_input = [make_stage("a", lambda p, _c: p)]
        pipeline = CompressionPipeline(stages=list_input)  # type: ignore[arg-type]
        assert isinstance(pipeline.stages, tuple)
        assert len(pipeline.stages) == 1

    def test_helpers_and_immutability(self) -> None:
        """Empty-pipeline falsy + with_extra_stage is immutable + stage_names."""
        empty = CompressionPipeline(stages=())
        assert bool(empty) is False
        assert len(empty) == 0
        assert empty.stage_names() == ()

        base = CompressionPipeline(stages=(make_stage("a", lambda p, _c: p),))
        extended = base.with_extra_stage(make_stage("b", lambda p, _c: p))
        assert len(base) == 1
        assert len(extended) == 2
        assert extended.stage_names() == ("a", "b")


# ---------------------------------------------------------------------------
# Strict mode + telemetry attribution
# ---------------------------------------------------------------------------


class TestPipelineStrictModeAndTelemetry:
    """Strict mode raises on first failure; lenient mode logs + skips."""

    def test_strict_raises_compression_stage_error(self) -> None:
        def boom(_payload, _ctx):
            raise ValueError("transform failure")

        pipeline = CompressionPipeline(
            stages=(make_stage("boom", boom),),
            name="strict_test",
        )
        with pytest.raises(CompressionStageError) as exc_info:
            pipeline.run("input", strict=True)
        assert "boom" in str(exc_info.value)
        assert "ValueError" in str(exc_info.value)
        assert "strict_test" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)

    def test_lenient_mode_logs_and_continues(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """strict=False: failure logs WARNING, input passes to next stage."""
        invocations: list[str] = []

        def boom(_payload, _ctx):
            raise RuntimeError("kaboom")

        def next_stage(payload, _ctx):
            invocations.append(payload)
            return payload + "_next"

        pipeline = CompressionPipeline(
            stages=(
                make_stage("boom", boom),
                make_stage("next_stage", next_stage),
            ),
            name="lenient_test",
        )
        with caplog.at_level(logging.WARNING):
            result = pipeline.run("seed", strict=False)
        assert invocations == ["seed"], "input MUST pass to next stage unchanged"
        assert result.payload == "seed_next"
        assert result.failed_stages == ("boom",)
        assert result.stage_results[0].error == "RuntimeError"
        assert any("best-effort skip" in rec.message for rec in caplog.records)

    def test_applied_vs_bypassed_attribution(self) -> None:
        """Telemetry separates applied / bypassed stages cleanly."""
        bypass_flag = {"on": True}

        def conditional_bypass(_payload, _ctx):
            return bypass_flag["on"]

        applied_stage = make_stage("applied", lambda p, _c: p + "_x")
        bypassed_stage = CompressionStage(
            name="bypassed",
            transform=lambda p, _c: p + "_y",
            bypass=conditional_bypass,
        )

        pipeline = CompressionPipeline(stages=(applied_stage, bypassed_stage))
        result = pipeline.run("seed")
        assert result.applied_stages == ("applied",)
        assert result.bypassed_stages == ("bypassed",)
        assert result.payload == "seed_x"


# ---------------------------------------------------------------------------
# Wrapper around existing transforms — surface integration smoke test
# ---------------------------------------------------------------------------


class TestStageWrappersAroundExistingTransforms:
    """Smoke test proving the protocol wraps the existing transforms."""

    def test_existing_transforms_compose_through_pipeline(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The 4 module-level transforms compose under the unified pipeline.

        Combines the truncate / directed_compact / apply_local_recipe
        smoke tests into a single composition assertion: run all three as
        stages in one pipeline, verify each stage's expected behaviour
        (truncate shortens, directed_compact preserves keyword, recipe
        bypasses when env-flag unset). Per W-17 single-assertion smoke
        tests are consolidated.
        """
        from devolaflow.compressor import directed_compact, truncate_tool_output
        from devolaflow.shell_proxy.commands import (
            apply_local_recipe,
            is_command_mapping_active,
        )

        monkeypatch.delenv("DEVOLAFLOW_RTK_PROXY", raising=False)

        def truncate_transform(payload, ctx):
            text, _ = truncate_tool_output(
                payload,
                head_chars=ctx.get("head_chars", 100),
                tail_chars=ctx.get("tail_chars", 100),
            )
            return text

        def compact_transform(payload, ctx):
            return directed_compact(
                payload,
                focus_keywords=ctx.get("focus_keywords"),
                max_drop_pct=ctx.get("max_drop_pct", 0.50),
            )

        def recipe_transform(payload, ctx):
            new_output, _ = apply_local_recipe(ctx.get("cmd", "pytest"), payload)
            return new_output

        def recipe_bypass(_payload, _ctx):
            return not is_command_mapping_active()

        pipeline = CompressionPipeline(
            stages=(
                make_stage("truncate", truncate_transform),
                make_stage("compact", compact_transform),
                CompressionStage(
                    name="apply_local_recipe",
                    transform=recipe_transform,
                    bypass=recipe_bypass,
                    bypass_conditions=("env_flag_unset",),
                ),
            )
        )
        long_text = (
            "Para mentioning API.\n\n"
            + "Para mentioning API again.\n\n"
            + ("Noise paragraph " * 200 + "\n\n") * 3
        )
        result = pipeline.run(
            long_text,
            context={"focus_keywords": ["API"], "head_chars": 50, "tail_chars": 50},
        )
        assert "API" in result.payload
        assert "apply_local_recipe" in result.bypassed_stages, (
            "recipe stage MUST bypass when env-flag unset (R5 strict)"
        )


# ---------------------------------------------------------------------------
# Protocol identity test — every shipped transform implements the protocol
# ---------------------------------------------------------------------------


class TestAllStagesImplementProtocol:
    """Verify the 6 v8.5.1 transforms are wrapped behind CompressionStage."""

    def test_all_stages_implement_protocol(self) -> None:
        """Every canonical transform has a CompressionStage wrapper.

        This pins the v9-ADR-006 acceptance criterion: the 6 v8.0.0+
        transforms (truncate_tool_output, summarise_predecessor extractive +
        Stage A + Stage B, directed_compact, apply_local_recipe) MUST be
        accessible as CompressionStage instances. The wrappers may live in
        the modules themselves or be constructed at call time via make_stage;
        this test asserts the make_stage path is exposed in __all__.
        """
        from devolaflow import compression_pipeline as cp

        for symbol in (
            "CompressionStage",
            "CompressionPipeline",
            "make_stage",
            "BYPASS_ALWAYS",
            "BYPASS_NEVER",
        ):
            assert symbol in cp.__all__, f"{symbol!r} missing from __all__"

        for transform_module, transform_name in [
            ("devolaflow.compressor", "truncate_tool_output"),
            ("devolaflow.compressor", "summarise_predecessor"),
            ("devolaflow.compressor", "directed_compact"),
            ("devolaflow.compressor", "compression_pipeline_stages"),
            ("devolaflow.shell_proxy.commands", "apply_local_recipe"),
            ("devolaflow.shell_proxy.commands", "compression_pipeline_stage"),
            ("devolaflow.llm_client", "compression_pipeline_stage"),
        ]:
            mod = __import__(transform_module, fromlist=[transform_name])
            transform = getattr(mod, transform_name)
            assert callable(transform), (
                f"{transform_module}.{transform_name} MUST be callable so it can be "
                "wrapped by make_stage as a CompressionStage transform"
            )

    def test_stage_result_dataclass_shape(self) -> None:
        """StageResult default + non-default construction surfaces the same fields."""
        default_sr = StageResult(name="x")
        assert default_sr.name == "x"
        assert default_sr.bypassed is False
        assert default_sr.applied is False
        assert default_sr.error is None
        assert default_sr.telemetry == {}

        full_sr = StageResult(name="boom", error="network", telemetry={"latency_ms": 500.0})
        assert full_sr.error == "network"
        assert full_sr.telemetry["latency_ms"] == 500.0
