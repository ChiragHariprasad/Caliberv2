"""Verification of conservative provenance metadata and declared dependencies.

Ensures that:
1. Runtime Kafka transport dependency (confluent-kafka) is explicitly declared.
2. Composed historical captures declare LAB regime rather than claiming unverified institutional provenance.
3. Legacy capture manifests explicitly declare data_regime=LAB.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_confluent_kafka_dependency_declared_in_pyproject() -> None:
    pyproject_path = ROOT / "backend" / "pyproject.toml"
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")
    assert "confluent-kafka" in content, "confluent-kafka must be declared in backend/pyproject.toml dependencies"


def test_confluent_kafka_dependency_declared_in_requirements() -> None:
    req_path = ROOT / "backend" / "requirements.txt"
    assert req_path.exists()
    content = req_path.read_text(encoding="utf-8")
    assert "confluent-kafka" in content, "confluent-kafka must be declared in backend/requirements.txt"


def test_historical_acquisition_declares_lab_regime() -> None:
    acquire_path = ROOT / "scripts" / "acquire_historical_race.py"
    assert acquire_path.exists()
    content = acquire_path.read_text(encoding="utf-8")
    assert '"data_regime": "LAB"' in content or '"data_regime": DataRegime.LAB' in content, (
        "scripts/acquire_historical_race.py must declare LAB regime for composed records"
    )
    assert 'VERIFIED_HISTORICAL_CAPTURE' not in content, (
        "scripts/acquire_historical_race.py must not assert unqualified VERIFIED_HISTORICAL_CAPTURE without institutional provenance"
    )


def test_silverstone_capture_manifest_declares_lab_regime() -> None:
    manifest_path = ROOT / "captures" / "f1-2023-silverstone-race" / "capture_manifest.json"
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data.get("data_regime") == "LAB", "f1-2023-silverstone-race capture_manifest.json must declare data_regime=LAB"

