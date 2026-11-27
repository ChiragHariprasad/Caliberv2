"""Explicit migration path from a legacy capture directory to a v4 archive."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .archive import create_bundle
from .durable import DataRegime, TimeScale, TimeScaleReference
from .source_pack import f1_reference_source_pack


def archive_legacy_capture(
    capture_dir: Path,
    destination: Path,
    *,
    regime: DataRegime = DataRegime.LAB,
    archive_id: str | None = None,
) -> Path:
    """Archive an existing PULSE capture without upgrading its evidence claim.

    The default is ``LAB`` because old capture folders lack the licence and
    lineage records needed to assert PUBLIC, LICENSED, or INSTITUTIONAL status.
    Callers must deliberately opt in to a different regime after source review.
    """
    capture_dir = Path(capture_dir)
    manifest_path = capture_dir / "capture_manifest.json"
    events_path = capture_dir / "envelopes.jsonl"
    if not manifest_path.is_file() or not events_path.is_file():
        raise FileNotFoundError("legacy capture must contain capture_manifest.json and envelopes.jsonl")
    capture = json.loads(manifest_path.read_text(encoding="utf-8"))
    identifier = archive_id or f"legacy-{capture.get('capture_id') or capture_dir.name}"
    source_pack = f1_reference_source_pack()
    if regime not in source_pack.pack.supported_regimes:
        raise ValueError(f"regime {regime.value} is not supported by the f1 reference pack")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep staging alongside the requested output. This works in restricted
    # environments and avoids assuming that the process-wide temp directory is
    # writable by the archive process.
    with tempfile.TemporaryDirectory(prefix=".calibre-capture-", dir=destination.parent) as tmp:
        staging = Path(tmp)
        source_pack_path = staging / "source-pack.json"
        source_pack_path.write_text(json.dumps(source_pack.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        references_path = staging / "effective-references.json"
        references_path.write_text("[]\n", encoding="utf-8")
        entries: list[tuple[Path, str, str]] = [
            (events_path, "raw/envelopes.jsonl", "application/x-ndjson"),
            (manifest_path, "legacy/capture_manifest.json", "application/json"),
            (source_pack_path, "pack/source-pack.json", "application/json"),
            (references_path, "references/effective-references.json", "application/json"),
        ]
        entry_list = capture_dir / "entry_list.json"
        if entry_list.is_file():
            entries.append((entry_list, "legacy/entry_list.json", "application/json"))
        return create_bundle(
            destination,
            entries,
            archive_id=identifier,
            pack=source_pack.pack,
            regime=regime,
            time_scale=TimeScaleReference(TimeScale.UTC, "ietf-leap-seconds", "2026-01"),
            reference_bindings=(),
        )
