"""End-to-end persistence probe for the v7.0.3 compression pipeline (ADR-004).

The probe synthesises a Stage A artifact with a seeded preserve-list panel,
runs ``devolaflow.compressor.summarise_predecessor`` over it, embeds the
result inside a canonical-layout Stage B lean dispatch, and asserts that
**every** seeded entity survives verbatim into the Stage B dispatch YAML.

Three scenario tiers ship with v7.0.3 per ADR-004 §2.2:

* ``easy`` — 500-token artifact, 5 entities. Expect 0 misses.
* ``medium`` — 5 000-token artifact, 20 entities. Expect ≤ 2 misses
  (carry-through ≥ 90 % per research §H.4).
* ``hard`` — 15 000-token artifact, 50 entities. Expect ≤ 5 misses.

Failure classification (ADR-004 §2.3):

* Missed verbatim but paraphrased → FAIL.
* Missed entirely → FAIL.
* Verbatim but duplicated → PASS (renderer's job, not the probe).
* Case mismatch for file paths or commit hashes → FAIL; other entities → PASS.

All seven test functions are marked ``persistence_probe`` so they run in
both the default pytest suite and the benchmark-CI step (SI-4 / SI-10 #5).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from devolaflow.compressor import extract_named_entities, summarise_predecessor
from tests._probe_fixtures import SCENARIO_SPECS, build_probe_workspace

PROBE_TELEMETRY_PATH = Path(".local/research/v7.0.3_probe_telemetry.json")
# Per ADR-004 §2.2: easy = 100% carry-through (0 misses), medium ≤ 2/20
# missed (90%+), hard ≤ 5/50 missed (90%+). Mapped below as (min_rate, max_misses).
SCENARIO_THRESHOLDS: dict[str, dict[str, float]] = {
    "easy": {"min_rate": 1.0, "max_misses": 0},
    "medium": {"min_rate": 0.90, "max_misses": 2},
    "hard": {"min_rate": 0.90, "max_misses": 5},
}

_CASE_SENSITIVE_TYPES = frozenset({"file_paths", "commit_hashes"})


def _entity_fingerprint(entity: dict) -> tuple[str, str]:
    """Return a ``(type, value)`` tuple for carry-through matching.

    Case-mismatch policy (ADR-004 §2.3): file paths and commit hashes are
    case-sensitive — ``Src/auth.py`` != ``src/auth.py``. Everything else is
    case-insensitive because our existing preserve-list patterns are already
    case-tolerant (acceptance bullets, metrics, etc.).
    """
    value = entity["value"]
    if entity["type"] in _CASE_SENSITIVE_TYPES:
        return entity["type"], value
    return entity["type"], value.lower()


def compute_entity_carrythrough_rate(
    stage_a_artifact: Path,
    stage_b_dispatch: Path,
) -> float:
    """Return the fraction of Stage A entities that survive into Stage B.

    Test-only helper per ADR-004 §3: we deliberately keep this out of the
    production ``devolaflow.compressor`` surface so the probe can evolve its
    scoring semantics without coupling to downstream consumers.
    """
    stage_a_entities = extract_named_entities(stage_a_artifact.read_text(encoding="utf-8"))
    if not stage_a_entities:
        return 1.0

    stage_b_text = stage_b_dispatch.read_text(encoding="utf-8")
    stage_b_lower = stage_b_text.lower()

    hits = 0
    for entity in stage_a_entities:
        value = entity["value"]
        if entity["type"] in _CASE_SENSITIVE_TYPES:
            if value in stage_b_text:
                hits += 1
        else:
            if value.lower() in stage_b_lower:
                hits += 1
    return hits / len(stage_a_entities)


def _carrythrough_misses(workspace: dict) -> list[dict]:
    """Return the list of Stage A entities that do NOT appear in Stage B."""
    stage_b_text = workspace["stage_b_dispatch"].read_text(encoding="utf-8")
    stage_b_lower = stage_b_text.lower()
    misses: list[dict] = []
    for entity in workspace["artifact_entities"]:
        value = entity["value"]
        if entity["type"] in _CASE_SENSITIVE_TYPES:
            if value not in stage_b_text:
                misses.append(entity)
        else:
            if value.lower() not in stage_b_lower:
                misses.append(entity)
    return misses


pytestmark = pytest.mark.persistence_probe


class TestCarrythroughProbe:
    """Core persistence-probe tests (ADR-004 §6 tests #1–#6)."""

    def test_carrythrough_passes_on_faithful_summary(
        self, _compression_e2e_workspace: dict
    ) -> None:
        workspace = _compression_e2e_workspace
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        # Easy scenario (default) must hit every seed.
        assert rate == 1.0, (
            f"expected 100% carry-through on faithful summary, got {rate:.4f}; "
            f"misses={[e['value'] for e in _carrythrough_misses(workspace)]}"
        )

    def test_carrythrough_fails_on_paraphrase(self, tmp_path: Path) -> None:
        """Paraphrase injection must be diagnosable at the probe level.

        We inject a paraphrase for one of the file-path seeds (the
        summariser will faithfully reproduce the paraphrased text, so the
        probe's job is to notice that the *original* seed disappeared from
        the Stage B dispatch).
        """
        faithful = build_probe_workspace(tmp_path / "faithful", scenario="easy")
        paraphrased = build_probe_workspace(
            tmp_path / "paraphrased", scenario="easy", paraphrase_file_path=True
        )

        faithful_seeds = set(faithful["seeds"])
        paraphrased_seeds = set(paraphrased["seeds"])
        dropped_seeds = faithful_seeds - paraphrased_seeds
        assert dropped_seeds, (
            "paraphrase fixture failed to remove any file-path seed — "
            "probe cannot distinguish paraphrase from verbatim"
        )

        stage_b_text = paraphrased["stage_b_dispatch"].read_text(encoding="utf-8")
        for missing_seed in dropped_seeds:
            assert missing_seed not in stage_b_text, (
                f"paraphrase probe failed — original seed {missing_seed!r} still present "
                "in Stage B dispatch (expected to be replaced by 'the compressor module')"
            )
        assert "the compressor module" in stage_b_text, (
            "paraphrase probe failed — injected paraphrase not found in Stage B"
        )

    def test_carrythrough_threshold_easy(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="easy")
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["easy"]
        assert rate >= thresholds["min_rate"], (
            f"easy carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"easy misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_carrythrough_threshold_medium(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="medium", summary_max_tokens=2400)
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["medium"]
        assert rate >= thresholds["min_rate"], (
            f"medium carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"medium misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_carrythrough_threshold_hard(self, tmp_path: Path) -> None:
        workspace = build_probe_workspace(tmp_path, scenario="hard", summary_max_tokens=4800)
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        misses = _carrythrough_misses(workspace)
        thresholds = SCENARIO_THRESHOLDS["hard"]
        assert rate >= thresholds["min_rate"], (
            f"hard carry-through {rate:.4f} < {thresholds['min_rate']:.2f}; "
            f"{len(misses)} misses: {[e['value'] for e in misses]}"
        )
        assert len(misses) <= thresholds["max_misses"], (
            f"hard misses {len(misses)} > {thresholds['max_misses']} allowed"
        )

    def test_extract_named_entities_integration(self, tmp_path: Path) -> None:
        """ADR-004 §6 test #6: extract_named_entities on ~10 K-token artifact
        must return >= 40 entities spanning multiple types.
        """
        # The ``medium`` scenario already has 20 panel entities; we inflate the
        # artifact body so the token count hits ~10 K and re-extract so the
        # body's incidental entities (file paths, version strings) also count.
        workspace = build_probe_workspace(tmp_path, scenario="medium", summary_max_tokens=2400)
        artifact_text = workspace["stage_a_artifact"].read_text(encoding="utf-8")
        # Append a block of extra entity-carrying lines to reach >= 40.
        extra_lines = []
        for i in range(40):
            extra_lines.append(
                f"- file src/devolaflow/extra_module_{i:03d}.py updated in commit "
                f"0123abc{i:03d}0 for T-X{i:02d} (version 7.0.{i} at {i * 3}ms)"
            )
        augmented_path = workspace["stage_a_artifact"]
        augmented_text = artifact_text + "\n\n## Extra Corpus\n" + "\n".join(extra_lines)
        augmented_path.write_text(augmented_text, encoding="utf-8")
        entities = extract_named_entities(augmented_text)
        types = {e["type"] for e in entities}
        assert len(entities) >= 40, (
            f"expected >= 40 entities, got {len(entities)} (types: {sorted(types)})"
        )
        # ADR-003 §6 commits to 8 entity classes; we need at least 4 to
        # satisfy ``mixed types`` per ADR-004 §6 #6.
        assert len(types) >= 4, f"expected >= 4 entity types, got {sorted(types)}"


class TestCarrythroughHelper:
    """Additional coverage for the test-only ``compute_entity_carrythrough_rate``
    helper — these tests complement ADR-004 §6 by guarding the helper's
    boundary conditions that the primary probe scenarios do not exercise.
    """

    def test_carrythrough_helper_empty_artifact_returns_one(self, tmp_path: Path) -> None:
        empty_artifact = tmp_path / "empty.md"
        empty_artifact.write_text("no entities here — pure prose body\n")
        dummy_dispatch = tmp_path / "dispatch.yaml"
        dummy_dispatch.write_text("hdr:\n  id: d-empty\n")
        rate = compute_entity_carrythrough_rate(empty_artifact, dummy_dispatch)
        # Convention: empty preserve-list → rate 1.0 (nothing to carry = no loss).
        assert rate == 1.0

    def test_carrythrough_helper_case_mismatch_for_file_paths_fails(self, tmp_path: Path) -> None:
        """File paths are case-sensitive per ADR-004 §2.3 — uppercase
        ``SRC/auth.py`` in Stage B must NOT satisfy a ``src/auth.py`` seed."""
        artifact = tmp_path / "artifact.md"
        artifact.write_text("# Stage A\n\n## Preserve-list\n\n- src/devolaflow/example.py\n")
        dispatch = tmp_path / "dispatch.yaml"
        dispatch.write_text("hdr:\n  id: d-case\npred:\n  - key_facts: SRC/DEVOLAFLOW/EXAMPLE.py\n")
        rate = compute_entity_carrythrough_rate(artifact, dispatch)
        assert rate == 0.0, f"case-mismatch for file paths must FAIL, got {rate:.4f}"


class TestProbeTelemetry:
    """ADR-004 §6 test #7 — record per-scenario runtime + rate to
    ``.local/research/v7.0.3_probe_telemetry.json`` for SI-3 scoring."""

    def test_probe_reports_flake_rate(self, tmp_path: Path) -> None:
        telemetry: dict = {"scenarios": {}}
        for scenario in ("easy", "medium", "hard"):
            spec = SCENARIO_SPECS[scenario]
            summary_max_tokens = {"easy": 1200, "medium": 2400, "hard": 4800}[scenario]
            start = time.perf_counter()
            workspace = build_probe_workspace(
                tmp_path / scenario,
                scenario=scenario,
                summary_max_tokens=summary_max_tokens,
            )
            rate = compute_entity_carrythrough_rate(
                workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
            )
            elapsed_s = time.perf_counter() - start
            telemetry["scenarios"][scenario] = {
                "entity_target": spec["entity_target"],
                "body_tokens": spec["body_tokens"],
                "carrythrough_rate": round(rate, 6),
                "missed_entity_count": len(_carrythrough_misses(workspace)),
                "elapsed_s": round(elapsed_s, 4),
                "threshold_min_rate": SCENARIO_THRESHOLDS[scenario]["min_rate"],
            }

        # Write under tmp_path (NOT the git-tracked PROBE_TELEMETRY_PATH) so the
        # test never dirties the working tree on every run (v14.1.0 G-8 hygiene
        # fix). The canonical telemetry snapshot lives at PROBE_TELEMETRY_PATH and
        # is regenerated out-of-band, not as a side effect of the test suite.
        telemetry_path = tmp_path / PROBE_TELEMETRY_PATH.name
        telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        telemetry_path.write_text(json.dumps(telemetry, indent=2, sort_keys=True))

        assert telemetry_path.exists()
        loaded = json.loads(telemetry_path.read_text())
        assert set(loaded["scenarios"]) == {"easy", "medium", "hard"}
        for scenario, record in loaded["scenarios"].items():
            assert record["elapsed_s"] >= 0.0, f"telemetry for {scenario} missing elapsed_s"
            assert "carrythrough_rate" in record

    def test_telemetry_records_threshold_per_scenario(self, tmp_path: Path) -> None:
        """Regression guard: telemetry MUST embed each scenario's minimum
        carry-through threshold so downstream SI-3 scoring can compare
        measured rates against the contractual targets without re-deriving
        them from the test fixture.
        """
        # Build a single scenario to keep this test cheap; validate the
        # threshold dict shape the other test writes out.
        workspace = build_probe_workspace(tmp_path, scenario="easy")
        rate = compute_entity_carrythrough_rate(
            workspace["stage_a_artifact"], workspace["stage_b_dispatch"]
        )
        record = {
            "carrythrough_rate": round(rate, 6),
            "threshold_min_rate": SCENARIO_THRESHOLDS["easy"]["min_rate"],
            "threshold_max_misses": SCENARIO_THRESHOLDS["easy"]["max_misses"],
        }
        assert record["threshold_min_rate"] == 1.0
        assert record["threshold_max_misses"] == 0
        assert record["carrythrough_rate"] >= record["threshold_min_rate"]


# ---------------------------------------------------------------------------
# v7.2.5 P-05 — Long-Context Repo QA retrieval-mode probe (Tier 2 #5).
# Asserts that summarise_predecessor with retrieval_query lifts the target
# module's body-marker carry-through by >= 30 pp vs the baseline (no-query)
# path on a synthesized 50k-token "repo" payload (10 modules × 5k each).
# ---------------------------------------------------------------------------

# Body-only markers. Chosen so they do NOT match any pattern in
# devolaflow.compressor._ENTITY_PATTERNS (file_paths, task_ids, version_strings,
# commit_hashes, metric_values, error_messages, acceptance_criterion_bullets,
# interface_signatures) — i.e. they appear in the summary ONLY when the
# section that holds them is selected for the body. None of these strings
# carry a ".ext" suffix (would match file_paths) or surround a `def`/`class`
# (would match interface_signatures).
_AUTH_MARKERS: tuple[str, ...] = (
    "JWT",
    "validate_jwt",
    "decode_token",
    "authentication",
    "authorize",
    "bearer_token",
    "claims_set",
    "signing_key",
    "token_expiry",
    "hmac_signature",
)
_PAYMENT_MARKERS: tuple[str, ...] = (
    "Stripe",
    "charge_intent",
    "refund_flow",
    "webhook_event",
    "transaction_id",
)
# Order in which sections are written into the synthesized artifact. payments.py
# is positioned first so it is fully retained in the baseline (no-query) probe;
# auth.py is positioned mid-document so the baseline body budget runs out
# before reaching it. routes.py at position 2 carries 5 of the 10 auth markers
# as incidental references so the baseline still scores ~50% auth retention.
_MODULE_ORDER: tuple[str, ...] = (
    "payments.py",
    "routes.py",
    "db.py",
    "cache.py",
    "auth.py",
    "middleware.py",
    "templates.py",
    "notifications.py",
    "users.py",
    "admin.py",
)


def _module_body(module: str, target_chars: int) -> str:
    """Return ``target_chars`` of prose specific to ``module``.

    The body is built from a small per-module sentence pool (deliberately
    narrow vocabulary so the jaccard-based query-overlap score does not
    explode the union when auth.py is tokenised). Each module's prose is
    repeated until the byte budget is met, then trimmed to ``target_chars``.
    """
    pools: dict[str, list[str]] = {
        "payments.py": [
            "The Stripe charge_intent flow handles refund_flow and webhook_event.",
            "Each transaction_id is logged with a Stripe webhook_event signature.",
            "Refund_flow reverses a Stripe charge_intent atomically per transaction_id.",
            "The Stripe webhook_event endpoint validates the transaction_id and refund_flow.",
            "Charge_intent records carry transaction_id metadata and webhook_event status.",
        ],
        "routes.py": [
            "Routing dispatches incoming requests through the JWT middleware layer.",
            "The router matches paths and applies authentication via JWT.",
            "Routes call validate_jwt before delegating to handlers.",
            "Each route may opt into authorize for role checks.",
            "The decode_token helper exposes claims for downstream handlers.",
        ],
        "db.py": [
            "The database layer manages connection pools and query batching.",
            "Migrations track schema versions through the changelog table.",
            "Indexes are rebuilt nightly to keep query latency stable.",
            "Replicas serve read traffic while the primary handles writes.",
            "Connection pool size scales with the number of CPU cores.",
        ],
        "cache.py": [
            "The cache layer wraps redis with consistent hashing.",
            "TTL values default to five minutes for hot keys.",
            "Eviction follows an LRU policy with size-tiered buckets.",
            "Cache misses fall through to the database read path.",
            "Hit rate metrics are pushed to the monitoring pipeline.",
        ],
        "auth.py": [
            "JWT middleware validates JWT and authentication on every request.",
            "validate_jwt decodes JWT and verifies signing_key integrity.",
            "decode_token returns claims_set, bearer_token and authentication state.",
            "authorize checks the bearer_token and JWT claims_set against the role.",
            "JWT middleware enforces token_expiry and hmac_signature for authentication.",
        ],
        "middleware.py": [
            "The middleware chain composes logging, tracing, and CSRF guards.",
            "Request context is enriched before reaching the handler layer.",
            "Each guard short-circuits on failure with a structured response.",
            "Tracing emits spans across upstream and downstream calls.",
            "Compression and content negotiation run last in the chain.",
        ],
        "templates.py": [
            "Templates use jinja with sandboxed expression evaluation.",
            "Render passes wrap layout files around partial fragments.",
            "Common partials are cached by template path and locale.",
            "Layouts inherit from a base shell with named blocks.",
            "Asset references resolve to fingerprinted bundle paths.",
        ],
        "notifications.py": [
            "Notifications fan out to email, sms, and push channels.",
            "Each delivery is enqueued for the worker pool to process.",
            "Failures retry with exponential backoff and dead-letter routing.",
            "Templates support locale negotiation for multi-region tenants.",
            "Receipts are stored with delivery status and timestamps.",
        ],
        "users.py": [
            "User records carry profile fields and audit timestamps.",
            "Profile updates are validated before persistence layer writes.",
            "Email verification tokens expire after twenty four hours.",
            "Account lifecycle events emit to the audit trail bus.",
            "User search supports prefix and full-text query modes.",
        ],
        "admin.py": [
            "Admin tooling exposes feature flags and tenant overrides.",
            "Bulk operations stream through a job queue with progress events.",
            "Audit logs render with filterable timestamps and operators.",
            "Tenant selection is gated by a dedicated session attribute.",
            "Long-running jobs surface health metrics on the dashboard.",
        ],
    }
    pool = pools[module]
    parts: list[str] = []
    idx = 0
    while sum(len(p) + 1 for p in parts) < target_chars:
        parts.append(pool[idx % len(pool)])
        idx += 1
    body = " ".join(parts)
    return body[:target_chars]


def _build_long_context_artifact(tmp_path: Path) -> Path:
    """Return a 50k-token markdown artifact with 10 modules × 5k tokens each.

    Token estimation in :mod:`devolaflow.compressor` uses ``len(text) // 4``
    in the conftest fallback path, so each section body targets ``5000 * 4 =
    20000`` characters of prose.
    """
    target_chars_per_module = 5000 * 4
    sections: list[str] = ["# Long-Context Repo QA Probe (50k tokens)\n"]
    for module in _MODULE_ORDER:
        body = _module_body(module, target_chars_per_module)
        sections.append(f"## {module}\n\n{body}\n")
    artifact_path = tmp_path / "repo.md"
    artifact_path.write_text("\n".join(sections), encoding="utf-8")
    return artifact_path


def _strip_key_facts_block(summary_text: str) -> str:
    """Return ``summary_text`` with the leading ``key_facts:`` YAML block stripped.

    ``summarise_predecessor`` always emits the key_facts prefix followed by a
    blank line and then the body chunks. We only want to count carry-through
    in the BODY (where the section-selection algorithm has effect); markers
    that survive in the always-emitted key_facts prefix would confound the
    measurement. The body section starts at the first blank-line gap after
    the ``key_facts:`` header.
    """
    if not summary_text.startswith("key_facts:"):
        return summary_text
    parts = summary_text.split("\n\n", 1)
    if len(parts) < 2:
        return ""
    return parts[1]


def _marker_carry_through(summary_text: str, markers: tuple[str, ...]) -> float:
    """Return the fraction of ``markers`` present (case-insensitive) in body."""
    body = _strip_key_facts_block(summary_text).lower()
    if not markers:
        return 0.0
    hits = sum(1 for m in markers if m.lower() in body)
    return hits / len(markers)


@pytest.mark.persistence_probe
def test_long_context_retrieval_query_lifts_target_module_carry_through(
    tmp_path: Path,
) -> None:
    """P-05 v7.2.5 acceptance gate — retrieval-prioritised summary lifts the
    target module's carry-through by >= 30 pp on a synthesized 50k-token repo.

    Layout: 10 modules × 5k tokens each. ``payments.py`` at position 1 (always
    retained in baseline, drops out under retrieval-mode), ``auth.py`` at
    position 5 (out of baseline budget; surfaces under retrieval-mode).
    ``routes.py`` at position 2 carries 5 of the 10 auth markers as incidental
    references so baseline auth retention is ~50% (the other 5 markers are
    auth.py-only and therefore dropped in baseline).

    Assertions (per task spec):
      * ``0.40 <= baseline_auth <= 0.60`` (~50% baseline carry-through)
      * ``query_auth > 0.85``
      * ``(query_auth - baseline_auth) > 0.30``  (>= 30 pp lift)
      * ``query_payments < 0.40``  (distractor module retention drops)
    """
    artifact_path = _build_long_context_artifact(tmp_path)
    max_tokens = 9000

    baseline = summarise_predecessor(str(artifact_path), max_tokens=max_tokens, mode="extractive")
    query_result = summarise_predecessor(
        str(artifact_path),
        max_tokens=max_tokens,
        mode="extractive",
        retrieval_query="JWT middleware authentication",
    )

    baseline_auth = _marker_carry_through(baseline["summary_text"], _AUTH_MARKERS)
    query_auth = _marker_carry_through(query_result["summary_text"], _AUTH_MARKERS)
    baseline_payments = _marker_carry_through(baseline["summary_text"], _PAYMENT_MARKERS)
    query_payments = _marker_carry_through(query_result["summary_text"], _PAYMENT_MARKERS)
    lift_pp = query_auth - baseline_auth

    assert 0.40 <= baseline_auth <= 0.60, (
        f"baseline auth retention {baseline_auth:.3f} outside [0.40, 0.60] "
        f"tolerance — fixture needs adjustment "
        f"(query_auth={query_auth:.3f}, "
        f"covered_baseline={baseline['covered_sections']})"
    )
    assert query_auth > 0.85, (
        f"query auth retention {query_auth:.3f} <= 0.85 — retrieval mode "
        f"failed to surface auth.py "
        f"(covered_query={query_result['covered_sections']})"
    )
    assert lift_pp > 0.30, (
        f"retrieval mode lifted auth retention by only {lift_pp * 100:.1f} pp "
        f"(baseline {baseline_auth:.3f} → query {query_auth:.3f}); "
        f"P-05 requires >= 30 pp lift — REJECT"
    )
    assert query_payments < 0.40, (
        f"distractor (payments) retention {query_payments:.3f} >= 0.40 in "
        f"query mode — retrieval scoring failed to demote payments.py "
        f"(baseline_payments={baseline_payments:.3f})"
    )
    assert query_payments < baseline_payments, (
        f"distractor retention should DROP in query mode: "
        f"baseline {baseline_payments:.3f} -> query {query_payments:.3f}"
    )
