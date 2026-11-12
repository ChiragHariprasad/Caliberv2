"""Create a CALIBRE v4 archive from a legacy PULSE capture directory."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permit `python scripts/archive_capture.py ...` from a source checkout without
# requiring a wheel installation. This is a command-entry concern; the core
# package itself has no path mutation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibre_core.capture_archive import archive_legacy_capture
from calibre_core.durable import DataRegime


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive a PULSE capture in the CALIBRE v4 format")
    parser.add_argument("capture_dir", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--archive-id")
    parser.add_argument("--regime", choices=[item.value for item in DataRegime], default=DataRegime.LAB.value)
    args = parser.parse_args()
    result = archive_legacy_capture(
        args.capture_dir,
        args.destination,
        archive_id=args.archive_id,
        regime=DataRegime(args.regime),
    )
    print(result)


if __name__ == "__main__":
    main()
