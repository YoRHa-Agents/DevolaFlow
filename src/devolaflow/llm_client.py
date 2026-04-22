"""Bounded LLM client wrapper for DevolaFlow Stage B abstractive summarisation.

v8.2.0 (PV-01) — Wraps an LLM API call with provider abstraction, latency
budget enforcement, and structured S-5 logging. The ``mock`` provider supplies
a deterministic response shape for tests; the ``openai`` and ``anthropic``
providers use lightweight ``urllib`` HTTP requests so no SDK dependency is
introduced (DevolaFlow's only runtime deps remain ``pyyaml`` + ``jsonschema``
per pyproject.toml).

Seven failure modes are recognised and logged structurally per
``S-5 No Silent Failures``:

  * ``timeout``           — wall-clock exceeded ``timeout_s``
  * ``network``           — HTTP / socket error (mapped from ``api_error``)
  * ``parse``             — output failed JSON / markdown shape parse
  * ``schema``            — output failed validation (e.g., missing entity)
  * ``content_filter``    — provider rejected for safety / policy reasons
  * ``rate_limit``        — provider returned 429 / cumulative cost overrun
  * ``fallback_disabled`` — caller explicitly opted out of Stage B (kill switch)

The Stage B caller (``devolaflow.compressor.summarise_predecessor`` invoked
with ``mode='abstractive'`` AND ``llm_assist=True``) consumes
:class:`LLMResponse` and pairs each failure with a Stage A heuristic fallback.

Design ref: ``.local/research/v8.0.0_p12_abstractive_stage_b_design.md`` §3-§5
            ``.local/research/v8.2.0_patch_plan.md`` §3 PV-01
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

__all__ = [
    "FAILURE_MODES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT_S",
    "PROVIDER_CHOICES",
    "LLMClientError",
    "LLMResponse",
    "LLMClient",
]

FAILURE_MODES: tuple[str, ...] = (
    "timeout",
    "network",
    "parse",
    "schema",
    "content_filter",
    "rate_limit",
    "fallback_disabled",
)
"""The seven canonical Stage B failure modes per S-5 (No Silent Failures).

Each mode maps to a structured log line via :meth:`LLMClient._log_failure`
and propagates to ``LLMResponse.error`` so the Stage B caller can branch
without exception handling. The set MUST stay frozen — adding a mode is
a CHANGELOG-visible behaviour change per CP-1 (No Ghost Features).
"""

PROVIDER_CHOICES: frozenset[str] = frozenset({"mock", "openai", "anthropic"})

DEFAULT_MAX_TOKENS: int = 2000
DEFAULT_TIMEOUT_S: float = 30.0

_DEFAULT_MODELS: dict[str, str] = {
    "mock": "mock-stage-b-v1",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
}

_API_KEY_ENV_VARS: dict[str, str] = {
    "mock": "DEVOLAFLOW_MOCK_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

_OPENAI_ENDPOINT: str = "https://api.openai.com/v1/chat/completions"
_ANTHROPIC_ENDPOINT: str = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION: str = "2023-06-01"


class LLMClientError(RuntimeError):
    """Raised when the :class:`LLMClient` cannot be constructed.

    The runtime path (:meth:`LLMClient.complete`) NEVER raises ad-hoc
    exceptions: it always returns an :class:`LLMResponse` whose ``error``
    field carries one of :data:`FAILURE_MODES` so callers can branch
    declaratively. This class is reserved for misconfiguration at
    construction time (unknown provider, non-positive timeout, etc.).
    """


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from a single :meth:`LLMClient.complete` call.

    Pure data: never holds I/O handles, callbacks, or mutable references.
    Safe to pickle, hash (entries are hashable), and store in a cache.

    Fields:
      * ``text``       — the model's text completion (empty on failure).
      * ``model``      — the model identifier used for the call (echoed
                         from :pyattr:`LLMClient.model`).
      * ``latency_ms`` — wall-clock latency of the API call in milliseconds
                         (computed via :func:`time.perf_counter` for
                         monotonic precision).
      * ``tokens_in``  — input tokens billed by the provider; ``0`` when
                         the provider does not report usage (mock).
      * ``tokens_out`` — output tokens billed.
      * ``error``      — ``None`` on success; otherwise one of
                         :data:`FAILURE_MODES`. Never a raw exception
                         string — callers can compare via equality.
    """

    text: str
    model: str
    latency_ms: float
    tokens_in: int
    tokens_out: int
    error: str | None


# ---------------------------------------------------------------------------
# MOCK provider — deterministic test fixture.
# ---------------------------------------------------------------------------
# The default MOCK handler emits a markdown block containing the verbatim
# entity list extracted from the prompt's ``VERBATIM ENTITIES (MUST appear
# character-for-character in your output):`` section followed by the first
# line of the Stage A snapshot. This guarantees:
#   * Determinism — same prompt → same text (no time, no randomness).
#   * CO-2 verbatim — every entity in the prompt's verbatim block appears
#     character-for-character in the output, so Stage B's entity diff check
#     never trips F4 by default.
# Tests inject custom mock_handlers to exercise specific failure modes.


def _default_mock_handler(prompt: str, model: str) -> LLMResponse:
    """Deterministic happy-path MOCK handler used by the test fixture.

    Extracts the ``VERBATIM ENTITIES`` block from ``prompt`` and the first
    non-blank line of the Stage A snapshot, and emits a single markdown
    block under ``## Stage B Mock Summary``. The output is ALWAYS shorter
    than typical ``max_tokens`` budgets and ALWAYS preserves entity values
    so Stage B's entity-preservation check passes by construction.
    """
    entities_block = _extract_block(prompt, marker="VERBATIM ENTITIES")
    stage_a_block = _extract_block(prompt, marker="Stage A snapshot")
    entity_lines = [line.strip() for line in entities_block.splitlines() if line.strip()]
    stage_a_lines = [
        line.strip()
        for line in stage_a_block.splitlines()
        if line.strip() and not line.strip().startswith("(")
    ]
    body_chunks: list[str] = ["## Stage B Mock Summary"]
    if entity_lines:
        body_chunks.append("entities: [" + ", ".join(entity_lines) + "]")
    if stage_a_lines:
        body_chunks.append(stage_a_lines[0])
    text = "\n".join(body_chunks)
    tokens_in = max(1, len(prompt) // 4)
    tokens_out = max(1, len(text) // 4)
    return LLMResponse(
        text=text,
        model=model,
        latency_ms=0.05,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        error=None,
    )


def _extract_block(prompt: str, *, marker: str) -> str:
    """Extract the body of a labelled prompt section after ``marker`` until a blank line.

    Used by the default mock handler to read the ``VERBATIM ENTITIES`` and
    ``Stage A snapshot`` blocks injected by
    :func:`devolaflow.compressor._build_stage_b_prompt`. Returns ``""`` when
    the marker is absent so the mock handler degrades gracefully on
    ad-hoc test prompts that don't follow the canonical layout.
    """
    if not isinstance(prompt, str) or marker not in prompt:
        return ""
    idx = prompt.index(marker)
    after = prompt[idx + len(marker) :]
    after = after.lstrip(":").lstrip()
    end = after.find("\n\n")
    if end == -1:
        return after
    return after[:end]


class LLMClient:
    """Bounded LLM client with provider abstraction and 7-mode error logging.

    Construction validates ``provider`` against :data:`PROVIDER_CHOICES`
    and rejects non-positive ``max_tokens`` / ``timeout_s`` (S-5). Once
    constructed, :meth:`complete` is the single entry point: it returns
    an :class:`LLMResponse` carrying either a successful text completion
    or one of the seven :data:`FAILURE_MODES` (never raises a network /
    parse exception to the caller — the Stage B integration relies on
    this contract for declarative fallback branching).

    Providers:
      * ``mock``      — deterministic; returns a fixed-shape response via
                        ``mock_handler`` (default :func:`_default_mock_handler`)
                        so unit tests are reproducible.
      * ``openai``    — ``POST {endpoint}/chat/completions`` via
                        :mod:`urllib.request`; requires ``OPENAI_API_KEY``
                        in env or ``api_key=`` kwarg.
      * ``anthropic`` — ``POST {endpoint}/messages``; requires
                        ``ANTHROPIC_API_KEY``.

    The deliberate avoidance of ``openai`` / ``anthropic`` SDKs keeps the
    runtime dependency surface tight (per pyproject.toml ``dependencies``).
    """

    def __init__(
        self,
        provider: Literal["mock", "openai", "anthropic"] = "mock",
        model: str | None = None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        mock_handler: Callable[[str, str], LLMResponse] | None = None,
    ) -> None:
        if provider not in PROVIDER_CHOICES:
            raise LLMClientError(
                f"unknown provider {provider!r}; expected one of {sorted(PROVIDER_CHOICES)}"
            )
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise LLMClientError(f"max_tokens must be a positive int (got {max_tokens!r})")
        if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
            raise LLMClientError(f"timeout_s must be > 0 (got {timeout_s!r})")
        self.provider: str = provider
        self.model: str = model or _DEFAULT_MODELS[provider]
        self.api_key: str | None = api_key or os.environ.get(_API_KEY_ENV_VARS[provider])
        self.max_tokens: int = max_tokens
        self.timeout_s: float = float(timeout_s)
        self._mock_handler: Callable[[str, str], LLMResponse] = (
            mock_handler if mock_handler is not None else _default_mock_handler
        )

    def complete(self, prompt: str) -> LLMResponse:
        """Issue a single LLM completion call against ``prompt``.

        Always returns an :class:`LLMResponse` — never raises. On any
        failure, the response's ``error`` field carries one of
        :data:`FAILURE_MODES` and a structured log entry is emitted via
        :meth:`_log_failure` so downstream auditors (Stage B EvoBench
        rollup, SI-4 regression analysis) can attribute the cause.

        Caller responsibilities (handled by
        :func:`devolaflow.compressor._invoke_stage_b_llm`):
          * Cost-ceiling enforcement (LLMClient is cost-aware via
            ``tokens_out`` reporting but does NOT track cumulative usage —
            that's a budget concern owned by ``gate/budget.py``).
          * Entity-preservation validation (F4 / schema fallback).
          * STAGE_B_ABORT detection in response text (F2 / fallback_disabled).
        """
        if not isinstance(prompt, str):
            return self._log_failure(
                "parse",
                detail=f"prompt must be str, got {type(prompt).__name__}",
                latency_ms=0.0,
            )
        dispatch = {
            "mock": self._complete_mock,
            "openai": self._complete_openai,
            "anthropic": self._complete_anthropic,
        }
        return dispatch[self.provider](prompt)

    def _complete_mock(self, prompt: str) -> LLMResponse:
        """Run the configured mock_handler with structured exception trapping.

        The default handler is :func:`_default_mock_handler` which emits a
        deterministic happy-path response. Tests inject custom handlers
        to simulate any of the seven failure modes (e.g., a handler that
        sleeps longer than ``timeout_s`` to trigger F1 timeout, a handler
        that returns ``error="rate_limit"`` to trigger F6, etc.).

        If the handler itself raises an exception the failure is mapped
        to ``parse`` (the handler returned malformed data) per S-5: never
        propagate raw exceptions across the LLMClient boundary.
        """
        start = time.perf_counter()
        try:
            response = self._mock_handler(prompt, self.model)
        except Exception as exc:  # noqa: BLE001 - intentional broad map per S-5
            return self._log_failure(
                "parse",
                detail=f"mock_handler raised {type(exc).__name__}: {exc}",
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
        latency_ms = (time.perf_counter() - start) * 1000.0
        if not isinstance(response, LLMResponse):
            return self._log_failure(
                "parse",
                detail=f"mock_handler returned {type(response).__name__}, not LLMResponse",
                latency_ms=latency_ms,
            )
        if latency_ms > self.timeout_s * 1000.0:
            return self._log_failure(
                "timeout",
                detail=(
                    f"mock_handler latency {latency_ms:.1f}ms exceeded "
                    f"timeout_s {self.timeout_s * 1000.0:.1f}ms"
                ),
                latency_ms=latency_ms,
            )
        if response.error is not None and response.error in FAILURE_MODES:
            self._log_failure_event(response.error, detail="mock_handler reported failure")
        return response

    def _complete_openai(self, prompt: str) -> LLMResponse:
        """POST a single chat-completion request to the OpenAI v1 endpoint."""
        if not self.api_key:
            return self._log_failure(
                "fallback_disabled",
                detail=f"missing api_key (env {_API_KEY_ENV_VARS['openai']})",
                latency_ms=0.0,
            )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
        }
        return self._post_json(
            url=_OPENAI_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            response_parser=_parse_openai_response,
        )

    def _complete_anthropic(self, prompt: str) -> LLMResponse:
        """POST a single messages request to the Anthropic v1 endpoint."""
        if not self.api_key:
            return self._log_failure(
                "fallback_disabled",
                detail=f"missing api_key (env {_API_KEY_ENV_VARS['anthropic']})",
                latency_ms=0.0,
            )
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        return self._post_json(
            url=_ANTHROPIC_ENDPOINT,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": _ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            payload=payload,
            response_parser=_parse_anthropic_response,
        )

    def _post_json(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        response_parser: Callable[[dict[str, Any], str], LLMResponse],
    ) -> LLMResponse:
        """Dispatch a JSON POST and map HTTP / parse failures to :data:`FAILURE_MODES`."""
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8")
        except TimeoutError as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return self._log_failure(
                "timeout", detail=f"urlopen timeout: {exc}", latency_ms=latency_ms
            )
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            if exc.code == 429:
                return self._log_failure(
                    "rate_limit",
                    detail=f"HTTP 429: {exc.reason}",
                    latency_ms=latency_ms,
                )
            if exc.code in (400, 422):
                return self._log_failure(
                    "content_filter",
                    detail=f"HTTP {exc.code}: {exc.reason}",
                    latency_ms=latency_ms,
                )
            return self._log_failure(
                "network",
                detail=f"HTTP {exc.code}: {exc.reason}",
                latency_ms=latency_ms,
            )
        except urllib.error.URLError as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return self._log_failure(
                "network", detail=f"URLError: {exc.reason}", latency_ms=latency_ms
            )
        except Exception as exc:  # noqa: BLE001 - S-5: never propagate raw exceptions
            latency_ms = (time.perf_counter() - start) * 1000.0
            return self._log_failure(
                "network", detail=f"{type(exc).__name__}: {exc}", latency_ms=latency_ms
            )
        latency_ms = (time.perf_counter() - start) * 1000.0
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            return self._log_failure(
                "parse", detail=f"json decode: {exc.msg}", latency_ms=latency_ms
            )
        try:
            return response_parser(data, self.model)
        except (KeyError, IndexError, TypeError) as exc:
            return self._log_failure(
                "schema",
                detail=f"response_parser {type(exc).__name__}: {exc}",
                latency_ms=latency_ms,
            )

    def _log_failure(self, mode: str, *, detail: str, latency_ms: float) -> LLMResponse:
        """Emit an S-5 structured log line and return a failure :class:`LLMResponse`."""
        self._log_failure_event(mode, detail=detail)
        return LLMResponse(
            text="",
            model=self.model,
            latency_ms=latency_ms,
            tokens_in=0,
            tokens_out=0,
            error=mode,
        )

    def _log_failure_event(self, mode: str, *, detail: str) -> None:
        """Emit a single structured WARNING log entry for a Stage B failure mode."""
        if mode not in FAILURE_MODES:
            raise LLMClientError(
                f"unknown failure mode {mode!r}; expected one of {sorted(FAILURE_MODES)}"
            )
        logger.warning(
            "llm_client.failure provider=%s model=%s mode=%s detail=%s",
            self.provider,
            self.model,
            mode,
            detail,
        )


def _parse_openai_response(data: dict[str, Any], model: str) -> LLMResponse:
    """Map an OpenAI chat-completion JSON to :class:`LLMResponse`."""
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return LLMResponse(
        text=str(text),
        model=str(data.get("model", model)),
        latency_ms=0.0,
        tokens_in=int(usage.get("prompt_tokens", 0)),
        tokens_out=int(usage.get("completion_tokens", 0)),
        error=None,
    )


def _parse_anthropic_response(data: dict[str, Any], model: str) -> LLMResponse:
    """Map an Anthropic messages-API JSON to :class:`LLMResponse`."""
    blocks = data["content"]
    text = "".join(block.get("text", "") for block in blocks if block.get("type") == "text")
    usage = data.get("usage", {})
    return LLMResponse(
        text=text,
        model=str(data.get("model", model)),
        latency_ms=0.0,
        tokens_in=int(usage.get("input_tokens", 0)),
        tokens_out=int(usage.get("output_tokens", 0)),
        error=None,
    )
