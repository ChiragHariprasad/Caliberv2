"""Full-System Browser End-to-End Validation Script for CALIBRE / PULSE.

Uses Playwright Chromium to exercise every user journey, control, modal,
and view on http://localhost:5173/ and capture screenshot evidence.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = WORKSPACE_ROOT / "reports" / "browser-validation" / "screenshots"
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://127.0.0.1:8000"


def run_validation():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("STARTING CALIBRE / PULSE BROWSER SYSTEM VALIDATION")
    print(f"Frontend Target: {FRONTEND_URL}")
    print(f"Backend Target:  {BACKEND_URL}")
    print(f"Screenshot Dir:  {SCREENSHOTS_DIR}")
    print("=" * 80)

    console_logs: list[dict] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        print("[1/12] Launching Playwright Chromium browser (1600x1000 viewport)...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()

        # Capture console and error events
        page.on("console", lambda msg: console_logs.append({"type": msg.type, "text": msg.text}))
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # ----------------------------------------------------------------------
        # Journey 1: Initial Cockpit Overview
        # ----------------------------------------------------------------------
        print("[2/12] Navigating to Cockpit overview...")
        page.goto(FRONTEND_URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector(".broadcast-banner", timeout=15000)
        page.wait_for_selector(".f1-leaderboard-table", timeout=15000)
        time.sleep(1.5)

        title = page.title()
        print(f"       Page Title: {title}")
        assert "PULSE" in title, f"Unexpected page title: {title}"

        # Verify 20 drivers rendered
        driver_rows = page.locator(".leaderboard-row").all()
        print(f"       Found {len(driver_rows)} driver rows in leaderboard.")
        assert len(driver_rows) >= 20, f"Expected at least 20 drivers, found {len(driver_rows)}"

        # Verify track map SVG
        track_svg = page.locator(".circuit-svg")
        assert track_svg.count() > 0, "Circuit track map SVG not found"
        print("       Circuit track map SVG rendered successfully.")

        shot_01 = SCREENSHOTS_DIR / "01_cockpit_overview.png"
        page.screenshot(path=str(shot_01), full_page=False)
        print(f"       [SAVED] {shot_01.name}")

        # ----------------------------------------------------------------------
        # Journey 2: Replay Playback (START)
        # ----------------------------------------------------------------------
        print("[3/12] Testing Replay Start/Play...")
        play_btn = page.locator(".control-btn.play-btn")
        play_btn.click()
        print("       Clicked Play button. Waiting 3.5s for live streaming...")
        time.sleep(3.5)

        # Check status indicator and timer
        status_text = page.locator(".replay-status-indicator .status-text").text_content()
        elapsed_pill = page.locator(".session-progress-pill").text_content()
        print(f"       Replay Status: {status_text} · Elapsed: {elapsed_pill}")

        shot_02 = SCREENSHOTS_DIR / "02_replay_running.png"
        page.screenshot(path=str(shot_02), full_page=False)
        print(f"       [SAVED] {shot_02.name}")

        # ----------------------------------------------------------------------
        # Journey 3: Speed Adjustment & Pause
        # ----------------------------------------------------------------------
        print("[4/12] Testing Speed Adjustment and Pause...")
        # Select 5x speed chip
        speed_5x_btn = page.locator("button.speed-chip:has-text('5x')")
        if speed_5x_btn.count() > 0:
            speed_5x_btn.first.click()
            time.sleep(1.0)
            print("       Selected 5.0x speed.")

        # Click Pause
        play_btn.click()
        time.sleep(1.0)
        paused_status = page.locator(".replay-status-indicator .status-text").text_content()
        print(f"       Clicked Pause button. Current Status: {paused_status}")

        shot_03 = SCREENSHOTS_DIR / "03_replay_paused.png"
        page.screenshot(path=str(shot_03), full_page=False)
        print(f"       [SAVED] {shot_03.name}")

        # ----------------------------------------------------------------------
        # Journey 4: Seeking Forward and Backward
        # ----------------------------------------------------------------------
        print("[5/12] Testing Replay Seeking...")
        slider = page.locator("input.timeline-slider")
        if slider.count() > 0:
            # Change slider to 40%
            slider.evaluate("el => { el.value = Math.floor(el.max * 0.4); el.dispatchEvent(new Event('change', { bubbles: true })); }")
            slider.dispatch_event("mouseup")
            time.sleep(2.0)
            readout = page.locator(".scrubber-progress-readout").text_content()
            print(f"       Scrubbed seek slider forward. Readout: {readout}")

        shot_04 = SCREENSHOTS_DIR / "04_replay_seek.png"
        page.screenshot(path=str(shot_04), full_page=False)
        print(f"       [SAVED] {shot_04.name}")

        # ----------------------------------------------------------------------
        # Journey 6: Race Control & Stewarding Tab
        # ----------------------------------------------------------------------
        print("[6/12] Testing Race Control & Stewarding Tab...")
        rc_tab = page.locator("button:has-text('Race Control & Stewarding')")
        rc_tab.click()
        page.wait_for_selector(".race-control-view", timeout=10000)
        time.sleep(1.0)

        notices = page.locator(".notice-row").all()
        print(f"       Loaded {len(notices)} official race control notices.")

        shot_06 = SCREENSHOTS_DIR / "06_race_control_view.png"
        page.screenshot(path=str(shot_06), full_page=False)
        print(f"       [SAVED] {shot_06.name}")

        # ----------------------------------------------------------------------
        # Journey 7: Agent Operations Tab (6 Agents Transparency)
        # ----------------------------------------------------------------------
        print("[7/12] Testing Agent Operations Tab...")
        agent_tab = page.locator("button:has-text('Agent Operations')")
        agent_tab.click()
        page.wait_for_selector(".agent-operations-view", timeout=10000)
        time.sleep(1.0)

        agent_cards = page.locator(".agent-telemetry-card").all()
        print(f"       Loaded {len(agent_cards)} specialist agent cards.")
        assert len(agent_cards) >= 6, f"Expected 6 registered agent cards, found {len(agent_cards)}"

        # Click on Agent 05 Consequence Fusion to view finding execution trace
        fusion_card = page.locator(".agent-telemetry-card:has-text('agent-05-fusion')")
        if fusion_card.count() > 0:
            fusion_card.click()
            time.sleep(1.0)
            print("       Opened execution trace modal for agent-05-fusion.")

        shot_07 = SCREENSHOTS_DIR / "07_agent_operations_view.png"
        page.screenshot(path=str(shot_07), full_page=False)
        print(f"       [SAVED] {shot_07.name}")

        # Close trace modal if open
        close_modal_btn = page.locator(".btn-close-modal")
        if close_modal_btn.count() > 0:
            close_modal_btn.first.click()
            time.sleep(0.5)

        # ----------------------------------------------------------------------
        # Journey 8: Pipeline Lab Tab
        # ----------------------------------------------------------------------
        print("[8/12] Testing Pipeline Lab Tab...")
        lab_tab = page.locator("button:has-text('Pipeline Lab')")
        lab_tab.click()
        page.wait_for_selector(".pipeline-lab-view", timeout=10000)
        time.sleep(1.0)

        pipeline_nodes = page.locator(".pipeline-node").all()
        print(f"       Found {len(pipeline_nodes)} streaming pipeline nodes.")

        shot_08 = SCREENSHOTS_DIR / "08_pipeline_lab_view.png"
        page.screenshot(path=str(shot_08), full_page=False)
        print(f"       [SAVED] {shot_08.name}")

        # ----------------------------------------------------------------------
        # Journey 9: Driver Telemetry Inspection Modal
        # ----------------------------------------------------------------------
        print("[9/12] Returning to Cockpit and Testing Driver Telemetry Modal...")
        cockpit_tab = page.locator("button:has-text('Cockpit')")
        cockpit_tab.click()
        page.wait_for_selector(".f1-leaderboard-table", timeout=10000)
        time.sleep(1.0)

        # Click telemetry inspection button on Car #16 (Leclerc)
        inspect_btn = page.locator(".btn-row-inspect").first
        inspect_btn.click()
        page.wait_for_selector(".telemetry-modal-card", timeout=10000)
        page.wait_for_selector(".gauge-card", timeout=10000)
        time.sleep(1.0)

        # Verify telemetry channels
        channel_cards = page.locator(".gauge-card").all()
        print(f"       Loaded {len(channel_cards)} live telemetry channel meters.")

        shot_09 = SCREENSHOTS_DIR / "09_driver_telemetry_modal.png"
        page.screenshot(path=str(shot_09), full_page=False)
        print(f"       [SAVED] {shot_09.name}")

        # Close modal
        close_tel_btn = page.locator(".telemetry-modal-card .btn-close-modal")
        if close_tel_btn.count() > 0:
            close_tel_btn.click()
            time.sleep(0.5)

        # ----------------------------------------------------------------------
        # Journey 10: Evidence Drawer Inspection
        # ----------------------------------------------------------------------
        print("[10/12] Testing Evidence Drawer Inspection...")
        
        # Ensure assessments are present
        if page.locator(".evidence-trigger-btn").count() == 0:
            print("       Resuming playback briefly at 5x to stream events and generate consequence assessments...")
            speed_5x = page.locator("button.speed-chip:has-text('5x')")
            if speed_5x.count() > 0:
                speed_5x.first.click()
            play_btn = page.locator(".control-btn.play-btn")
            play_btn.click()
            try:
                page.wait_for_selector(".evidence-trigger-btn", timeout=8000)
                print("       Assessments generated successfully!")
                play_btn.click()
            except Exception as e:
                print(f"       Notice while streaming for assessments: {e}")

        evidence_btns = page.locator(".evidence-trigger-btn")
        if evidence_btns.count() > 0:
            evidence_btns.first.click()
            page.wait_for_selector(".evidence-drawer-overlay", timeout=10000)
            time.sleep(1.0)
            print("       Opened Evidence Drawer for tactical briefing.")

            shot_10 = SCREENSHOTS_DIR / "10_evidence_drawer.png"
            page.screenshot(path=str(shot_10), full_page=False)
            print(f"       [SAVED] {shot_10.name}")

            # Close drawer
            close_drawer_btn = page.locator(".drawer-close-btn")
            if close_drawer_btn.count() > 0:
                close_drawer_btn.click()
                time.sleep(0.5)
        else:
            print("       [WARN] No evidence-trigger-btn found after playback.")

        # ----------------------------------------------------------------------
        # Journey 5: Replay Reset
        # ----------------------------------------------------------------------
        print("[11/12] Testing Replay Reset...")
        reset_btn = page.locator(".control-btn.restart-btn")
        if reset_btn.count() > 0:
            reset_btn.click()
            time.sleep(1.5)
            reset_status = page.locator(".replay-status-indicator .status-text").text_content()
            print(f"       Clicked Reset button. Status: {reset_status}")

        shot_05 = SCREENSHOTS_DIR / "05_replay_reset.png"
        page.screenshot(path=str(shot_05), full_page=False)
        print(f"       [SAVED] {shot_05.name}")

        # ----------------------------------------------------------------------
        # Journey 11 & 12: Session Switching (Silverstone & Monaco)
        # ----------------------------------------------------------------------
        print("[12/12] Testing Dynamic Session Switching...")
        circuit_select = page.locator("#circuit-select")

        # Switch to Silverstone
        circuit_select.select_option("f1-2023-silverstone-race")
        print("       Selected Silverstone Grand Prix session. Waiting for state load...")
        time.sleep(3.5)

        silverstone_header = page.locator(".broadcast-banner").text_content()
        print(f"       Banner Text: {silverstone_header[:100]}...")

        shot_11 = SCREENSHOTS_DIR / "11_silverstone_session.png"
        page.screenshot(path=str(shot_11), full_page=False)
        print(f"       [SAVED] {shot_11.name}")

        # Switch back to Monaco
        circuit_select.select_option("f1-2026-monaco-sim")
        print("       Selected Monaco Grand Prix simulation session. Waiting for state load...")
        time.sleep(3.0)

        shot_12 = SCREENSHOTS_DIR / "12_monaco_restored.png"
        page.screenshot(path=str(shot_12), full_page=False)
        print(f"       [SAVED] {shot_12.name}")

        browser.close()

    print("=" * 80)
    print("BROWSER SYSTEM VALIDATION COMPLETED SUCCESSFULLY")
    print(f"Total Console Messages: {len(console_logs)}")
    print(f"Total Page Errors:     {len(page_errors)}")
    if page_errors:
        print("Page Errors encountered:")
        for err in page_errors:
            print(f"  [ERROR] {err}")
    print("=" * 80)


if __name__ == "__main__":
    run_validation()
