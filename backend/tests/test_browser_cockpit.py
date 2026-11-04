"""Verification of browser cockpit screenshots and UI artifacts."""

from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = WORKSPACE_ROOT / "docs" / "screenshots"


def test_captured_cockpit_screenshots_exist_and_non_empty():
    """Verify that all 6 required high-resolution cockpit screenshots were generated."""
    expected_screenshots = [
        "01_cockpit_monaco.png",
        "02_driver_telemetry_modal.png",
        "03_race_control_stewarding.png",
        "04_agent_operations.png",
        "05_pipeline_lab.png",
        "06_cockpit_silverstone.png",
    ]

    assert SCREENSHOTS_DIR.exists(), f"Screenshots directory missing at {SCREENSHOTS_DIR}"

    for shot_name in expected_screenshots:
        shot_path = SCREENSHOTS_DIR / shot_name
        assert shot_path.exists(), f"Screenshot {shot_name} was not generated"
        size = shot_path.stat().st_size
        assert size > 50_000, f"Screenshot {shot_name} too small ({size} bytes), may be blank"

