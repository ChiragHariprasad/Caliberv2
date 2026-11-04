from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from pulse.testing.orchestrator import VerticalSliceVerifier


def setup_cli_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="PULSE End-to-End Pipeline Verification Runner")
    parser.add_argument("--session-id", default=None, help="Session identifier for verification run")
    parser.add_argument("--mode", default="REPLAY", choices=["REPLAY", "SIMULATED", "LIVE"], help="Test execution mode")
    parser.add_argument("--output-dir", default="reports", help="Directory where verification artifacts will be generated")
    parser.add_argument("--broker", default=None, help="Kafka bootstrap broker address (defaults to PULSE_KAFKA_BOOTSTRAP_SERVERS)")

    args = parser.parse_args()
    setup_cli_logging()

    verifier = VerticalSliceVerifier(
        session_id=args.session_id,
        mode=args.mode,
        output_dir=args.output_dir,
        broker_bootstrap=args.broker,
    )

    try:
        res = asyncio.run(verifier.run())
        print(f"\n[E2E SUCCESS] All {len(res.stages)} stages passed with 100% reconciliation.")
        print(f"Artifacts written to: {res.artifacts.get('e2e_report.md')}")
        sys.exit(0)
    except Exception as e:
        print(f"\n[E2E FAILED] Execution error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

