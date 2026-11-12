"""Portable CALIBRE archive bundles; object storage is the record, not Kafka."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .durable import CANONICALIZATION_VERSION, DataRegime, DomainPack, TimeScaleReference, digest_bytes, digest_json, validate_digest


MANIFEST_NAME = "calibre-manifest.json"
VERIFIER_NAME = "verify_bundle.py"
SCHEMA = "calibre.archive.manifest/1.0"


@dataclass(frozen=True)
class ArchiveEntry:
    path: str
    media_type: str
    size_bytes: int
    digest: str

    def to_dict(self) -> dict[str, str | int]:
        return {"path": self.path, "media_type": self.media_type, "size_bytes": self.size_bytes, "digest": self.digest}


def _safe_relative(path: str) -> Path:
    result = Path(path)
    if result.is_absolute() or ".." in result.parts or result == Path("."):
        raise ValueError(f"archive entry path is unsafe: {path!r}")
    return result


def create_bundle(
    destination: Path,
    entries: Iterable[tuple[Path, str, str]],
    *,
    archive_id: str,
    pack: DomainPack,
    regime: DataRegime,
    time_scale: TimeScaleReference,
    execution_profile: str = "batch-v1",
    evaluator_capsule: str = "python-stdlib-verifier/1",
    reference_bindings: Iterable[str] = (),
) -> Path:
    """Create a self-verifying, immutable-format bundle from explicit files.

    Existing destinations are rejected to prevent an archive from being silently
    amended after a manifest has been issued.
    """
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"archive destination already exists: {destination}")
    if not archive_id:
        raise ValueError("archive_id is required")
    destination.mkdir(parents=True)
    result: list[ArchiveEntry] = []
    try:
        for source, stored_path, media_type in entries:
            source = Path(source)
            if not source.is_file():
                raise FileNotFoundError(source)
            relative = _safe_relative(stored_path)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            payload = target.read_bytes()
            result.append(ArchiveEntry(relative.as_posix(), media_type, len(payload), digest_bytes(payload)))
        if not result:
            raise ValueError("an archive requires at least one payload entry")
        result.sort(key=lambda entry: entry.path)
        binding_items = tuple(reference_bindings)
        bindings = sorted(set(binding_items))
        if len(bindings) != len(binding_items):
            raise ValueError("reference bindings must be unique")
        manifest = {
            "schema": SCHEMA,
            "archive_id": archive_id,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "canonicalization": CANONICALIZATION_VERSION,
            "pack": pack.to_dict(),
            "data_regime": regime.value,
            "time_scale": time_scale.to_dict(),
            "execution_profile": execution_profile,
            "evaluator_capsule": evaluator_capsule,
            "reference_bindings": bindings,
            "entries": [entry.to_dict() for entry in result],
        }
        manifest["manifest_digest"] = digest_json(manifest)
        (destination / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verifier = Path(__file__).with_name("standalone_verifier.py")
        shutil.copyfile(verifier, destination / VERIFIER_NAME)
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return destination


def verify_manifest(bundle: Path) -> list[str]:
    bundle = Path(bundle)
    manifest_path = bundle / MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest is unreadable: {exc}"]
    failures: list[str] = []
    if manifest.get("schema") != SCHEMA:
        failures.append("unsupported manifest schema")
    digest = manifest.get("manifest_digest")
    copy = dict(manifest)
    copy.pop("manifest_digest", None)
    try:
        if validate_digest(str(digest)) != digest_json(copy):
            failures.append("manifest digest mismatch")
    except ValueError:
        failures.append("manifest digest is not tagged sha256")
    for item in manifest.get("entries", []):
        try:
            relative = _safe_relative(str(item["path"]))
            payload = (bundle / relative).read_bytes()
            if len(payload) != item["size_bytes"]:
                failures.append(f"size mismatch: {relative.as_posix()}")
            if digest_bytes(payload) != validate_digest(str(item["digest"])):
                failures.append(f"digest mismatch: {relative.as_posix()}")
        except (KeyError, OSError, ValueError, TypeError) as exc:
            failures.append(f"invalid entry: {exc}")
    return failures
