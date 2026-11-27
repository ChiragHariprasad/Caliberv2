"""Verification of browser cockpit screenshots and UI artifacts."""

from pathlib import Path
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = WORKSPACE_ROOT / "reports" / "browser-validation" / "screenshots"


def test_captured_cockpit_screenshots_exist_and_non_empty():
    """Verify that all required high-resolution cockpit screenshots were generated."""
    expected_screenshots = [
        "01_cockpit_overview.png",
        "02_replay_running.png",
        "03_replay_paused.png",
        "04_replay_seek.png",
        "05_replay_reset.png",
        "06_race_control_view.png",
        "07_agent_operations_view.png",
        "08_pipeline_lab_view.png",
        "09_driver_telemetry_modal.png",
        "10_evidence_drawer.png",
        "11_silverstone_session.png",
        "12_monaco_restored.png",
    ]

    assert SCREENSHOTS_DIR.exists(), f"Screenshots directory missing at {SCREENSHOTS_DIR}"

    for shot_name in expected_screenshots:
        shot_path = SCREENSHOTS_DIR / shot_name
        assert shot_path.exists(), f"Screenshot {shot_name} was not generated"
        size = shot_path.stat().st_size
        assert size > 50_000, f"Screenshot {shot_name} too small ({size} bytes), may be blank"

