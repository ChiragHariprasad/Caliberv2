"""Standard-library-only verifier copied into every CALIBRE archive bundle."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def verify(bundle: Path) -> list[str]:
    try:
        manifest = json.loads((bundle / "calibre-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest is unreadable: {exc}"]
    failures: list[str] = []
    if manifest.get("schema") != "calibre.archive.manifest/1.0":
        failures.append("unsupported manifest schema")
    supplied = manifest.pop("manifest_digest", None)
    canonical = json.dumps(manifest, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if supplied != _digest(canonical):
        failures.append("manifest digest mismatch")
    for entry in manifest.get("entries", []):
        try:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("unsafe path")
            data = (bundle / relative).read_bytes()
            if len(data) != entry["size_bytes"]:
                failures.append(f"size mismatch: {relative.as_posix()}")
            if entry["digest"] != _digest(data):
                failures.append(f"digest mismatch: {relative.as_posix()}")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            failures.append(f"invalid entry: {exc}")
    return failures


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(__file__).resolve().parent
    errors = verify(target)
    if errors:
        print("FAILED")
        print("\n".join(errors))
        raise SystemExit(1)
    print("OK")
