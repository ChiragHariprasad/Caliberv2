from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from calibre_core.archive import create_bundle, verify_manifest
from calibre_core.batch import ArchiveVerificationError, BatchProfile
from calibre_core.capture_archive import archive_legacy_capture
from calibre_core.durable import DataRegime, DomainPack, TimeScale, TimeScaleReference, digest_bytes, validate_digest, threshold_witness
from calibre_core.references import EffectiveReference, ReferenceRegistry
from calibre_core.source_pack import f1_reference_source_pack


def pack() -> DomainPack:
    return DomainPack(
        "f1-reference",
        "1.0.0",
        ("event", "session", "asset", "segment"),
        (DataRegime.PUBLIC, DataRegime.LAB, DataRegime.INSTITUTIONAL),
    )


def test_digests_are_algorithm_tagged_and_legacy_is_explicit() -> None:
    digest = digest_bytes(b"calibre")
    assert digest.startswith("sha256:")
    assert validate_digest(digest) == digest
    with pytest.raises(ValueError):
        validate_digest(digest.removeprefix("sha256:"))
    assert validate_digest(digest.removeprefix("sha256:"), allow_legacy_bare_sha256=True) == digest


def test_guard_band_is_policy_neutral() -> None:
    witness = threshold_witness(60.1, 60.0, observed_uncertainty=0.11)
    assert witness.classification == "INDETERMINATE"
    assert threshold_witness(60.3, 60.0, observed_uncertainty=0.11).classification == "ABOVE_THRESHOLD"
    assert threshold_witness(59.7, 60.0, observed_uncertainty=0.11).classification == "BELOW_THRESHOLD"


def test_effective_references_select_by_date_and_reject_ambiguity() -> None:
    at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    registry = ReferenceRegistry(pack())
    old = EffectiveReference("limit-80", "pit_speed_limit", {"event": "monaco"}, 80, "kph", at, at + timedelta(days=10))
    current = EffectiveReference("limit-60", "pit_speed_limit", {"event": "monaco"}, 60, "kph", at + timedelta(days=10))
    registry.add(old)
    registry.add(current)
    assert registry.resolve("pit_speed_limit", {"event": "monaco", "session": "race"}, at).value == 80
    assert registry.resolve("pit_speed_limit", {"event": "monaco"}, at + timedelta(days=10)).value == 60
    with pytest.raises(ValueError, match="ambiguous"):
        registry.add(EffectiveReference("duplicate-window", "pit_speed_limit", {"event": "monaco"}, 70, "kph", at))
        registry.resolve("pit_speed_limit", {"event": "monaco"}, at + timedelta(days=10))


def test_bundle_verifies_without_project_dependencies(tmp_path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text('{"event":"example"}\n', encoding="utf-8")
    bundle = create_bundle(
        tmp_path / "archive",
        [(source, "raw/events.jsonl", "application/x-ndjson")],
        archive_id="lab-example-001",
        pack=pack(),
        regime=DataRegime.LAB,
        time_scale=TimeScaleReference(TimeScale.UTC, "ietf-leap-seconds", "2026-01"),
    )
    assert verify_manifest(bundle) == []
    completed = subprocess.run(
        [sys.executable, str(bundle / "verify_bundle.py"), str(bundle)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stdout.strip() == "OK"


def test_bundle_detects_payload_tampering(tmp_path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text('{"event":"example"}\n', encoding="utf-8")
    bundle = create_bundle(
        tmp_path / "archive",
        [(source, "raw/events.jsonl", "application/x-ndjson")],
        archive_id="lab-example-002",
        pack=pack(),
        regime=DataRegime.LAB,
        time_scale=TimeScaleReference(TimeScale.UTC, "ietf-leap-seconds", "2026-01"),
    )
    (bundle / "raw" / "events.jsonl").write_text('{"event":"changed"}\n', encoding="utf-8")
    assert verify_manifest(bundle) == ["digest mismatch: raw/events.jsonl"]


def test_batch_profile_replay_is_deterministic_and_checks_the_archive(tmp_path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text('{"event_id":"b","value":2}\n{"event_id":"a","value":1}\n', encoding="utf-8")
    bundle = create_bundle(
        tmp_path / "archive",
        [(source, "raw/events.jsonl", "application/x-ndjson")],
        archive_id="lab-replay-001",
        pack=pack(),
        regime=DataRegime.LAB,
        time_scale=TimeScaleReference(TimeScale.UTC, "ietf-leap-seconds", "2026-01"),
        reference_bindings=("rules-2026.1",),
    )
    profile = BatchProfile()
    assert profile.replay(bundle) == profile.replay(bundle)
    assert profile.replay(bundle).input_record_count == 2
    (bundle / "raw" / "events.jsonl").write_text("broken\n", encoding="utf-8")
    with pytest.raises(ArchiveVerificationError, match="archive verification failed"):
        profile.replay(bundle)


def test_source_pack_makes_shared_public_lineage_non_independent() -> None:
    source_pack = f1_reference_source_pack()
    assert not source_pack.independent("PITWALL", "TRACINGINSIGHTS", DataRegime.PUBLIC)
    assert source_pack.independent("INSTITUTIONAL_LOOP_A", "INSTITUTIONAL_LOOP_B", DataRegime.INSTITUTIONAL)
    assert "INDEPENDENT_CORROBORATION_WHEN_PROVEN" not in source_pack.allowed_claims(DataRegime.PUBLIC)
    assert "INDEPENDENT_CORROBORATION_WHEN_PROVEN" in source_pack.allowed_claims(DataRegime.INSTITUTIONAL)


def test_legacy_capture_archive_defaults_to_lab_and_is_replayable(tmp_path) -> None:
    capture = tmp_path / "legacy-capture"
    capture.mkdir()
    (capture / "capture_manifest.json").write_text('{"capture_id":"demo-capture"}\n', encoding="utf-8")
    (capture / "envelopes.jsonl").write_text('{"event_id":"one","value":1}\n', encoding="utf-8")
    archive = archive_legacy_capture(capture, tmp_path / "archive")
    assert verify_manifest(archive) == []
    manifest = (archive / "calibre-manifest.json").read_text(encoding="utf-8")
    assert '"data_regime": "LAB"' in manifest
    assert BatchProfile().replay(archive).input_record_count == 1
