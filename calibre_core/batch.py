"""Mandatory deterministic batch execution profile for archive replays."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .archive import MANIFEST_NAME, verify_manifest
from .durable import canonical_json, digest_bytes, digest_json


class ArchiveVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class BatchReplayResult:
    profile: str
    archive_id: str
    manifest_digest: str
    input_record_count: int
    ordered_record_digest: str
    result_digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "archive_id": self.archive_id,
            "manifest_digest": self.manifest_digest,
            "input_record_count": self.input_record_count,
            "ordered_record_digest": self.ordered_record_digest,
            "result_digest": self.result_digest,
        }


class BatchProfile:
    """A pure archive-to-result profile with no network, wall clock, or broker.

    This first v4 profile deliberately establishes deterministic replay and
    input accounting. Domain evaluation is plugged in only after Spec v1.0
    defines the evaluator boundary.
    """

    name = "batch-v1"

    def replay(self, bundle: Path) -> BatchReplayResult:
        bundle = Path(bundle)
        failures = verify_manifest(bundle)
        if failures:
            raise ArchiveVerificationError("archive verification failed: " + "; ".join(failures))
        manifest = json.loads((bundle / MANIFEST_NAME).read_text(encoding="utf-8"))
        record_digests: list[str] = []
        for entry in manifest["entries"]:
            if entry["media_type"] != "application/x-ndjson":
                continue
            for number, line in enumerate((bundle / entry["path"]).read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ArchiveVerificationError(f"invalid JSON record in {entry['path']}:{number}") from exc
                if not isinstance(record, dict):
                    raise ArchiveVerificationError(f"record in {entry['path']}:{number} is not an object")
                record_digests.append(digest_bytes(canonical_json(record)))
        ordered = digest_json(record_digests)
        result = {
            "profile": self.name,
            "archive_id": manifest["archive_id"],
            "manifest_digest": manifest["manifest_digest"],
            "input_record_count": len(record_digests),
            "ordered_record_digest": ordered,
        }
        return BatchReplayResult(
            profile=self.name,
            archive_id=manifest["archive_id"],
            manifest_digest=manifest["manifest_digest"],
            input_record_count=len(record_digests),
            ordered_record_digest=ordered,
            result_digest=digest_json(result),
        )
