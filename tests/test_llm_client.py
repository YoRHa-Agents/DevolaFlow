"""Tests for the v8.2.0 PV-01 bounded LLM client wrapper.

Covers the :class:`devolaflow.llm_client.LLMClient` construction surface,
the deterministic ``mock`` provider, the seven canonical failure-mode
log emissions per S-5, and the LLMResponse dataclass contract.
"""

from __future__ import annotations

import json
import logging
import time

import pytest

from devolaflow.llm_client import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_S,
    FAILURE_MODES,
    PROVIDER_CHOICES,
    LLMClient,
    LLMClientError,
    LLMResponse,
)


class TestFailureModesContract:
    """The seven canonical Stage B failure modes are immutable + complete."""

    def test_failure_modes_count_is_exactly_seven(self) -> None:
        assert len(FAILURE_MODES) == 7, (
            f"FAILURE_MODES count drifted; expected 7 per S-5/PV-01 AC #3, got {len(FAILURE_MODES)}"
        )

    def test_failure_modes_are_canonical_set(self) -> None:
        assert set(FAILURE_MODES) == {
            "timeout",
            "network",
            "parse",
            "schema",
            "content_filter",
            "rate_limit",
            "fallback_disabled",
        }

    def test_failure_modes_is_tuple_immutable(self) -> None:
        assert isinstance(FAILURE_MODES, tuple)

    def test_provider_choices_are_canonical_three(self) -> None:
        assert frozenset({"mock", "openai", "anthropic"}) == PROVIDER_CHOICES


class TestConstructionValidation:
    """LLMClient construction rejects misconfiguration per S-5."""

    def test_default_provider_is_mock(self) -> None:
        client = LLMClient()
        assert client.provider == "mock"
        assert client.max_tokens == DEFAULT_MAX_TOKENS
        assert client.timeout_s == DEFAULT_TIMEOUT_S

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(LLMClientError) as exc_info:
            LLMClient(provider="grok")  # type: ignore[arg-type]
        assert "unknown provider" in str(exc_info.value)

    def test_zero_max_tokens_rejected(self) -> None:
        with pytest.raises(LLMClientError):
            LLMClient(provider="mock", max_tokens=0)

    def test_negative_timeout_rejected(self) -> None:
        with pytest.raises(LLMClientError):
            LLMClient(provider="mock", timeout_s=-1)

    def test_default_model_per_provider(self) -> None:
        for provider in ("mock", "openai", "anthropic"):
            client = LLMClient(provider=provider)  # type: ignore[arg-type]
            assert client.model, f"{provider} default model must not be empty"

    def test_explicit_model_override(self) -> None:
        client = LLMClient(provider="mock", model="custom-test-model")
        assert client.model == "custom-test-model"

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")
        client = LLMClient(provider="openai")
        assert client.api_key == "sk-test-from-env"

    def test_api_key_kwarg_wins_over_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-from-env")
        client = LLMClient(provider="openai", api_key="sk-explicit-kwarg")
        assert client.api_key == "sk-explicit-kwarg"


class TestLLMResponseContract:
    """LLMResponse is a frozen dataclass with the canonical 6-field shape."""

    def test_response_is_frozen(self) -> None:
        response = LLMResponse(
            text="x",
            model="m",
            latency_ms=1.0,
            tokens_in=2,
            tokens_out=3,
            error=None,
        )
        with pytest.raises((AttributeError, Exception)):
            response.text = "y"  # type: ignore[misc]

    def test_response_has_six_canonical_fields(self) -> None:
        from dataclasses import fields

        names = {f.name for f in fields(LLMResponse)}
        assert names == {"text", "model", "latency_ms", "tokens_in", "tokens_out", "error"}

    def test_response_with_error_has_empty_text(self) -> None:
        response = LLMResponse(
            text="",
            model="m",
            latency_ms=0.0,
            tokens_in=0,
            tokens_out=0,
            error="timeout",
        )
        assert response.error == "timeout"
        assert response.text == ""


class TestMockProviderDeterministic:
    """The default mock_handler is deterministic + entity-preserving."""

    def test_mock_complete_returns_response(self) -> None:
        client = LLMClient(provider="mock")
        result = client.complete("hello world")
        assert isinstance(result, LLMResponse)
        assert result.error is None

    def test_mock_complete_is_deterministic_across_calls(self) -> None:
        client = LLMClient(provider="mock")
        a = client.complete("identical prompt")
        b = client.complete("identical prompt")
        assert a.text == b.text
        assert a.tokens_in == b.tokens_in
        assert a.tokens_out == b.tokens_out

    def test_mock_complete_preserves_verbatim_entities_block(self) -> None:
        prompt = (
            "VERBATIM ENTITIES (MUST appear character-for-character in your output):\n"
            "  - src/auth.py\n"
            "  - 9.0.2\n"
            "  - abc1234\n"
            "\n"
            "Stage A snapshot (use as a HINT, not as ground truth):\n"
            "## Decision\n"
            "Use src/auth.py at 9.0.2 commit abc1234.\n"
        )
        client = LLMClient(provider="mock")
        result = client.complete(prompt)
        assert "src/auth.py" in result.text
        assert "9.0.2" in result.text
        assert "abc1234" in result.text

    def test_mock_complete_non_string_prompt_returns_parse_error(self) -> None:
        client = LLMClient(provider="mock")
        result = client.complete(123)  # type: ignore[arg-type]
        assert result.error == "parse"
        assert result.text == ""


class TestMockHandlerInjection:
    """Tests inject custom mock_handlers to exercise each failure mode."""

    @staticmethod
    def _handler_returning(error: str):
        def _handler(prompt: str, model: str) -> LLMResponse:
            return LLMResponse(
                text="",
                model=model,
                latency_ms=1.0,
                tokens_in=10,
                tokens_out=0,
                error=error,
            )

        return _handler

    @pytest.mark.parametrize("mode", list(FAILURE_MODES))
    def test_each_failure_mode_logs_warning(
        self,
        mode: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        client = LLMClient(provider="mock", mock_handler=self._handler_returning(mode))
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            response = client.complete("anything")
        assert response.error == mode
        assert any(f"mode={mode}" in record.getMessage() for record in caplog.records), (
            f"expected log line with mode={mode}; got {[r.getMessage() for r in caplog.records]!r}"
        )

    def test_mock_handler_raising_returns_parse_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _bad_handler(prompt: str, model: str) -> LLMResponse:
            raise RuntimeError("simulated handler crash")

        client = LLMClient(provider="mock", mock_handler=_bad_handler)
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "parse"
        assert any("RuntimeError" in record.getMessage() for record in caplog.records)

    def test_mock_handler_returning_non_response_logs_parse_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _bad_handler(prompt: str, model: str):
            return "not an LLMResponse"

        client = LLMClient(provider="mock", mock_handler=_bad_handler)  # type: ignore[arg-type]
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "parse"

    def test_mock_handler_exceeding_timeout_logs_timeout(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _slow_handler(prompt: str, model: str) -> LLMResponse:
            time.sleep(0.05)
            return LLMResponse(
                text="late",
                model=model,
                latency_ms=50.0,
                tokens_in=1,
                tokens_out=1,
                error=None,
            )

        client = LLMClient(provider="mock", mock_handler=_slow_handler, timeout_s=0.001)
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "timeout"


class TestProviderHttpFallbackDisabled:
    """openai / anthropic providers fall back when no API key is configured."""

    def test_openai_without_api_key_returns_fallback_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        client = LLMClient(provider="openai", api_key=None)
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "fallback_disabled"

    def test_anthropic_without_api_key_returns_fallback_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        client = LLMClient(provider="anthropic", api_key=None)
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "fallback_disabled"


class TestLogStructure:
    """The S-5 structured log line carries provider/model/mode/detail."""

    def test_log_record_contains_provider_and_model(self, caplog: pytest.LogCaptureFixture) -> None:
        client = LLMClient(
            provider="mock",
            model="test-model-x",
            mock_handler=TestMockHandlerInjection._handler_returning("network"),
        )
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            client.complete("hello")
        joined = "\n".join(record.getMessage() for record in caplog.records)
        assert "provider=mock" in joined
        assert "model=test-model-x" in joined
        assert "mode=network" in joined

    def test_log_failure_event_rejects_unknown_mode(self) -> None:
        client = LLMClient(provider="mock")
        with pytest.raises(LLMClientError):
            client._log_failure_event("not_a_mode", detail="x")


class TestHttpProviderPaths:
    """openai / anthropic providers cover the full _post_json HTTP fan-out."""

    @staticmethod
    def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, side_effect):
        import urllib.request as urlreq

        def _fake(*args, **kwargs):
            return side_effect(*args, **kwargs)

        monkeypatch.setattr(urlreq, "urlopen", _fake)

    @staticmethod
    def _fake_response(body: bytes):
        class _FakeResponse:
            def read(self) -> bytes:
                return body

            def __enter__(self):
                return self

            def __exit__(self, *exc) -> None:
                return None

        return _FakeResponse()

    def test_openai_success_path_parses_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = json.dumps(
            {
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "## Hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
        ).encode("utf-8")
        self._patch_urlopen(monkeypatch, lambda *a, **k: self._fake_response(body))
        client = LLMClient(provider="openai", api_key="sk-test")
        result = client.complete("hello")
        assert result.error is None
        assert result.text == "## Hello"
        assert result.tokens_in == 5
        assert result.tokens_out == 2

    def test_anthropic_success_path_parses_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = json.dumps(
            {
                "model": "claude-3-5-sonnet-20241022",
                "content": [{"type": "text", "text": "## Hello"}],
                "usage": {"input_tokens": 7, "output_tokens": 3},
            }
        ).encode("utf-8")
        self._patch_urlopen(monkeypatch, lambda *a, **k: self._fake_response(body))
        client = LLMClient(provider="anthropic", api_key="sk-test")
        result = client.complete("hello")
        assert result.error is None
        assert result.text == "## Hello"
        assert result.tokens_in == 7
        assert result.tokens_out == 3

    def test_http_429_maps_to_rate_limit(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import urllib.error

        def _raise_429(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="https://api/", code=429, msg="Too Many", hdrs=None, fp=None
            )

        self._patch_urlopen(monkeypatch, _raise_429)
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "rate_limit"

    def test_http_400_maps_to_content_filter(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import urllib.error

        def _raise_400(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="https://api/", code=400, msg="Bad Req", hdrs=None, fp=None
            )

        self._patch_urlopen(monkeypatch, _raise_400)
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "content_filter"

    def test_http_500_maps_to_network(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import urllib.error

        def _raise_500(*args, **kwargs):
            raise urllib.error.HTTPError(
                url="https://api/", code=500, msg="Internal", hdrs=None, fp=None
            )

        self._patch_urlopen(monkeypatch, _raise_500)
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "network"

    def test_url_error_maps_to_network(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import urllib.error

        def _raise_urlerror(*args, **kwargs):
            raise urllib.error.URLError("DNS failure")

        self._patch_urlopen(monkeypatch, _raise_urlerror)
        client = LLMClient(provider="anthropic", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "network"

    def test_timeout_error_maps_to_timeout(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _raise_timeout(*args, **kwargs):
            raise TimeoutError("read timed out")

        self._patch_urlopen(monkeypatch, _raise_timeout)
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "timeout"

    def test_invalid_json_maps_to_parse(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._patch_urlopen(monkeypatch, lambda *a, **k: self._fake_response(b"not valid json"))
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "parse"

    def test_response_parser_keyerror_maps_to_schema(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        body = json.dumps({"unexpected": "shape"}).encode("utf-8")
        self._patch_urlopen(monkeypatch, lambda *a, **k: self._fake_response(body))
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "schema"

    def test_unexpected_exception_maps_to_network(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def _raise_random(*args, **kwargs):
            raise ConnectionResetError("peer reset")

        self._patch_urlopen(monkeypatch, _raise_random)
        client = LLMClient(provider="openai", api_key="sk-test")
        with caplog.at_level(logging.WARNING, logger="devolaflow.llm_client"):
            result = client.complete("hello")
        assert result.error == "network"


class TestPromptHelpers:
    """Coverage for the small prompt-block / mock-handler helpers."""

    def test_extract_block_returns_empty_for_missing_marker(self) -> None:
        from devolaflow.llm_client import _extract_block

        assert _extract_block("body without marker", marker="ABSENT") == ""
        assert _extract_block(123, marker="ABSENT") == ""  # type: ignore[arg-type]

    def test_extract_block_returns_until_blank_line(self) -> None:
        from devolaflow.llm_client import _extract_block

        text = "MARK: line 1\nline 2\n\nrest"
        out = _extract_block(text, marker="MARK")
        assert "line 1" in out
        assert "line 2" in out
        assert "rest" not in out

    def test_default_mock_handler_handles_empty_blocks(self) -> None:
        from devolaflow.llm_client import _default_mock_handler

        response = _default_mock_handler("", "model-x")
        assert response.error is None
        assert response.text.startswith("## Stage B Mock Summary")
