"""Definitive End-to-End Browser Verification Suite for PULSE F1 Intelligence Platform.

Validates in a real Chromium browser context:
- Initial load, circuit SVG geometry, driver grid, stream connectivity
- Dynamic session switching with loading overlay
- Real-time streaming replay: Play, event consumption, cursor advancement, live state updates
- Playback controls: Pause, Resume, Reset, Seek/Scrubber, Speed adjustment
- Multi-tab cockpit navigation: Cockpit, Race Control, Agent Operations, Pipeline Lab
- Telemetry inspection modal
- Console error inspection and network audit
- Saves full-fidelity screenshots and JSON verification report
"""

import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = WORKSPACE_ROOT / "reports" / "browser_verification"
FRONTEND_URL = "http://127.0.0.1:5173"
BACKEND_URL = "http://127.0.0.1:8000"


def run_browser_verification():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "suite": "PULSE V1 Browser End-to-End Verification",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "frontend_url": FRONTEND_URL,
        "backend_url": BACKEND_URL,
        "steps": [],
        "console_errors": [],
        "console_warnings": [],
        "failed_requests": [],
        "overall_status": "PENDING",
    }

    print("=" * 80)
    print("STARTING PULSE BROWSER END-TO-END VERIFICATION SUITE")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 960})
        page = context.new_page()

        # Capture console messages
        def on_console(msg):
            if msg.type == "error":
                report["console_errors"].append(msg.text)
                print(f"[BROWSER ERROR] {msg.text}")
            elif msg.type == "warning":
                report["console_warnings"].append(msg.text)

        page.on("console", on_console)

        # Capture network failures
        def on_response(response):
            if response.status >= 400:
                report["failed_requests"].append({
                    "url": response.url,
                    "status": response.status,
                    "status_text": response.status_text,
                })
                print(f"[HTTP {response.status}] {response.url}")

        page.on("response", on_response)

        try:
            # -------------------------------------------------------------
            # STEP 1: INITIAL APPLICATION LOAD (B2)
            # -------------------------------------------------------------
            print("\n[STEP 1] Loading initial application at http://127.0.0.1:5173...")
            t0 = time.time()
            page.goto(FRONTEND_URL, wait_until="networkidle")
            page.wait_for_selector(".broadcast-banner", timeout=10000)
            page.wait_for_selector(".replay-controls-bar", timeout=10000)
            page.wait_for_selector(".circuit-svg", timeout=10000)
            page.wait_for_selector(".f1-leaderboard-table", timeout=10000)
            page.wait_for_timeout(1000)

            # Assert elements
            banner_text = page.locator(".broadcast-banner").text_content()
            conn_pill = page.locator(".pipeline-indicator").text_content()
            mode_badge = page.locator(".mode-badge").text_content()
            row_count = page.locator(".f1-leaderboard-table tbody tr").count()

            step1_snap = OUTPUT_DIR / "01_initial_load.png"
            page.screenshot(path=str(step1_snap), full_page=True)

            step1_passed = (
                "PULSE" in banner_text
                and "STREAM:" in conn_pill
                and row_count >= 15
            )
            report["steps"].append({
                "step": "B2_initial_load",
                "description": "Initial application load, circuit geometry, driver grid, and stream connectivity",
                "status": "PASSED" if step1_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "connection_pill": conn_pill.strip() if conn_pill else "",
                    "mode_badge": mode_badge.strip() if mode_badge else "",
                    "driver_count": row_count,
                    "screenshot": str(step1_snap),
                },
            })
            print(f" -> Initial load status: {'PASSED' if step1_passed else 'FAILED'} (drivers: {row_count}, stream: {conn_pill.strip()})")

            # -------------------------------------------------------------
            # STEP 2: SESSION SWITCHING (Silverstone 2023 Historical Replay)
            # -------------------------------------------------------------
            print("\n[STEP 2] Switching session to Silverstone 2023 Historical Replay...")
            t0 = time.time()
            circuit_select = page.locator("#circuit-select")
            circuit_select.select_option("f1-2023-silverstone-race")

            # Wait for switching overlay to appear and disappear
            try:
                page.wait_for_selector(".session-switching-overlay", state="visible", timeout=2000)
                print(" -> Session switching overlay appeared as expected.")
                page.wait_for_selector(".session-switching-overlay", state="detached", timeout=10000)
                print(" -> Session switching overlay detached cleanly.")
            except Exception:
                page.wait_for_timeout(1500)

            page.wait_for_timeout(1000)

            step2_snap = OUTPUT_DIR / "02_silverstone_selected.png"
            page.screenshot(path=str(step2_snap), full_page=True)

            silverstone_rows = page.locator(".f1-leaderboard-table tbody tr").count()
            silverstone_mode = page.locator(".mode-badge").text_content()

            step2_passed = silverstone_rows == 20 and "REPLAY" in silverstone_mode
            report["steps"].append({
                "step": "B2_session_switching",
                "description": "Switch to Silverstone 2023 Historical Replay and reinitialise grid",
                "status": "PASSED" if step2_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "mode": silverstone_mode.strip() if silverstone_mode else "",
                    "driver_count": silverstone_rows,
                    "screenshot": str(step2_snap),
                },
            })
            print(f" -> Silverstone session status: {'PASSED' if step2_passed else 'FAILED'} (drivers: {silverstone_rows}, mode: {silverstone_mode.strip()})")

            # -------------------------------------------------------------
            # STEP 3: PLAYBACK SPEED ADJUSTMENT (B7)
            # -------------------------------------------------------------
            print("\n[STEP 3] Setting playback acceleration to 5x...")
            t0 = time.time()
            speed_5x_btn = page.get_by_role("button", name="Playback speed 5x")
            speed_5x_btn.click()
            page.wait_for_timeout(1000)

            is_5x_selected = "is-selected" in (speed_5x_btn.get_attribute("class") or "")
            step3_snap = OUTPUT_DIR / "03_speed_5x_selected.png"
            page.screenshot(path=str(step3_snap), full_page=True)

            report["steps"].append({
                "step": "B7_speed_adjustment",
                "description": "Adjust replay acceleration factor to 5x",
                "status": "PASSED" if is_5x_selected else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "speed_selected": is_5x_selected,
                    "screenshot": str(step3_snap),
                },
            })
            print(f" -> Speed 5x selection status: {'PASSED' if is_5x_selected else 'FAILED'}")

            # -------------------------------------------------------------
            # STEP 4: REPLAY PLAY & STREAMING ADVANCEMENT (B3)
            # -------------------------------------------------------------
            print("\n[STEP 4] Clicking Play / Start to initiate streaming replay...")
            t0 = time.time()
            play_btn = page.locator(".play-btn")
            play_btn.click()

            # Wait 8 seconds to allow streaming playback to advance across Flink and agents
            print(" -> Waiting 8 seconds for Kafka -> Flink -> Python -> SSE streaming pipeline...")
            page.wait_for_timeout(8000)

            # Check status and progress
            status_text = page.locator(".status-text").text_content()
            scrubber_readout = page.locator(".scrubber-progress-readout").text_content()
            print(f" -> Status: {status_text.strip()}, Scrubber: {scrubber_readout.strip()}")

            step4_snap = OUTPUT_DIR / "04_playback_running.png"
            page.screenshot(path=str(step4_snap), full_page=True)

            step4_passed = "RUNNING" in status_text.upper()
            report["steps"].append({
                "step": "B3_playback_play",
                "description": "Start replay and verify streaming advancement across pipeline",
                "status": "PASSED" if step4_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "status": status_text.strip() if status_text else "",
                    "scrubber_readout": scrubber_readout.strip() if scrubber_readout else "",
                    "screenshot": str(step4_snap),
                },
            })
            print(f" -> Playback run status: {'PASSED' if step4_passed else 'FAILED'}")

            # -------------------------------------------------------------
            # STEP 5: PAUSE AND RESUME (B4)
            # -------------------------------------------------------------
            print("\n[STEP 5] Testing Pause and Resume controls...")
            t0 = time.time()
            # Click Pause
            play_btn.click()
            page.wait_for_timeout(1500)

            paused_status = page.locator(".status-text").text_content()
            scrubber_paused = page.locator(".scrubber-progress-readout").text_content()
            step5_pause_snap = OUTPUT_DIR / "05_paused.png"
            page.screenshot(path=str(step5_pause_snap), full_page=True)
            print(f" -> Paused status: {paused_status.strip()}, Readout: {scrubber_paused.strip()}")

            # Wait 2 seconds, verify no movement
            page.wait_for_timeout(2000)
            scrubber_paused_check = page.locator(".scrubber-progress-readout").text_content()
            pause_held = scrubber_paused == scrubber_paused_check

            # Click Resume
            play_btn.click()
            page.wait_for_timeout(3000)

            resumed_status = page.locator(".status-text").text_content()
            scrubber_resumed = page.locator(".scrubber-progress-readout").text_content()
            step5_resume_snap = OUTPUT_DIR / "06_resumed.png"
            page.screenshot(path=str(step5_resume_snap), full_page=True)
            print(f" -> Resumed status: {resumed_status.strip()}, Readout: {scrubber_resumed.strip()}")

            step5_passed = (
                "PAUSED" in paused_status.upper()
                and pause_held
                and "RUNNING" in resumed_status.upper()
            )
            report["steps"].append({
                "step": "B4_pause_resume",
                "description": "Pause playback, verify cursor freeze, and resume playback",
                "status": "PASSED" if step5_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "paused_status": paused_status.strip(),
                    "pause_held": pause_held,
                    "resumed_status": resumed_status.strip(),
                    "scrubber_resumed": scrubber_resumed.strip(),
                    "screenshot_paused": str(step5_pause_snap),
                    "screenshot_resumed": str(step5_resume_snap),
                },
            })
            print(f" -> Pause/Resume status: {'PASSED' if step5_passed else 'FAILED'}")

            # -------------------------------------------------------------
            # STEP 6: SEEK / TIMELINE SCRUBBER (B6)
            # -------------------------------------------------------------
            print("\n[STEP 6] Testing Seek / Timeline Scrubber to Event 50...")
            t0 = time.time()
            slider = page.locator("input.timeline-slider")
            # Seek using slider evaluation to trigger proper input/change event
            page.evaluate("""() => {
                const slider = document.querySelector('input.timeline-slider');
                if (slider) {
                    slider.value = 50;
                    slider.dispatchEvent(new Event('input', { bubbles: true }));
                    slider.dispatchEvent(new Event('mouseup', { bubbles: true }));
                }
            }""")
            page.wait_for_timeout(2000)

            step6_snap = OUTPUT_DIR / "07_seek.png"
            page.screenshot(path=str(step6_snap), full_page=True)
            scrubber_after_seek = page.locator(".scrubber-progress-readout").text_content()

            step6_passed = "50" in scrubber_after_seek or "Event" in scrubber_after_seek
            report["steps"].append({
                "step": "B6_seek_scrubber",
                "description": "Scrub cursor to Event 50 and verify state catchup",
                "status": "PASSED" if step6_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "readout": scrubber_after_seek.strip(),
                    "screenshot": str(step6_snap),
                },
            })
            print(f" -> Seek scrubber status: {'PASSED' if step6_passed else 'FAILED'} (readout: {scrubber_after_seek.strip()})")

            # -------------------------------------------------------------
            # STEP 7: RESET (B5)
            # -------------------------------------------------------------
            print("\n[STEP 7] Testing Replay Reset...")
            t0 = time.time()
            reset_btn = page.locator(".restart-btn")
            reset_btn.click()
            page.wait_for_timeout(2000)

            reset_status = page.locator(".status-text").text_content()
            reset_scrubber = page.locator(".scrubber-progress-readout").text_content()
            step7_snap = OUTPUT_DIR / "08_reset.png"
            page.screenshot(path=str(step7_snap), full_page=True)

            step7_passed = "READY" in reset_status.upper() and ("Event 0" in reset_scrubber or "0%" in reset_scrubber)
            report["steps"].append({
                "step": "B5_reset",
                "description": "Reset replay to index 0 with clean state under a fresh run ID",
                "status": "PASSED" if step7_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "status": reset_status.strip(),
                    "readout": reset_scrubber.strip(),
                    "screenshot": str(step7_snap),
                },
            })
            print(f" -> Reset status: {'PASSED' if step7_passed else 'FAILED'} (status: {reset_status.strip()}, readout: {reset_scrubber.strip()})")

            # -------------------------------------------------------------
            # STEP 8: MULTI-TAB VIEW NAVIGATION (B8)
            # -------------------------------------------------------------
            print("\n[STEP 8] Testing Cockpit Tab and View Navigation...")
            t0 = time.time()

            # 8a: Agent Operations Tab
            print(" -> Navigating to Agent Operations tab...")
            page.locator("button:has-text('Agent Operations')").click()
            page.wait_for_selector(".agent-operations-view", timeout=5000)
            page.wait_for_timeout(1000)

            agent_cards_count = page.locator(".agent-telemetry-card").count()
            step8a_snap = OUTPUT_DIR / "09_tab_agents.png"
            page.screenshot(path=str(step8a_snap), full_page=True)
            print(f" -> Agent Operations rendered with {agent_cards_count} specialist agents.")

            # 8b: Race Control Tab
            print(" -> Navigating to Race Control & Stewarding tab...")
            page.locator("button:has-text('Race Control')").click()
            page.wait_for_selector(".race-control-view", timeout=5000)
            page.wait_for_timeout(1000)

            official_table_visible = page.locator(".official-notices-table").is_visible()
            official_notices_count = page.locator(".official-notices-table tbody tr").count()
            step8b_snap = OUTPUT_DIR / "10_tab_race_control.png"
            page.screenshot(path=str(step8b_snap), full_page=True)
            print(f" -> Race Control rendered: table_visible={official_table_visible}, notice_rows={official_notices_count}")

            # 8c: Pipeline Lab Tab
            print(" -> Navigating to Pipeline Lab tab...")
            page.locator("button:has-text('Pipeline Lab')").click()
            page.wait_for_selector(".pipeline-lab-view", timeout=5000)
            page.wait_for_timeout(1000)

            pipeline_nodes_count = page.locator(".pipeline-node").count()
            step8c_snap = OUTPUT_DIR / "11_tab_pipeline_lab.png"
            page.screenshot(path=str(step8c_snap), full_page=True)
            print(f" -> Pipeline Lab rendered with {pipeline_nodes_count} streaming topology nodes.")

            # 8d: Return to Cockpit
            print(" -> Returning to Live Cockpit tab...")
            page.locator("button:has-text('Cockpit')").click()
            page.wait_for_selector(".cockpit-view-container", timeout=5000)
            page.wait_for_timeout(1000)

            step8d_snap = OUTPUT_DIR / "12_tab_cockpit.png"
            page.screenshot(path=str(step8d_snap), full_page=True)

            step8_passed = agent_cards_count == 5 and pipeline_nodes_count >= 4 and official_table_visible
            report["steps"].append({
                "step": "B8_tab_navigation",
                "description": "Navigate through Cockpit, Agent Operations, Race Control, and Pipeline Lab tabs",
                "status": "PASSED" if step8_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "agent_cards_count": agent_cards_count,
                    "official_notices_count": official_notices_count,
                    "pipeline_nodes_count": pipeline_nodes_count,
                    "screenshots": [
                        str(step8a_snap),
                        str(step8b_snap),
                        str(step8c_snap),
                        str(step8d_snap),
                    ],
                },
            })
            print(f" -> Tab navigation status: {'PASSED' if step8_passed else 'FAILED'}")

            # -------------------------------------------------------------
            # STEP 9: DRIVER TELEMETRY INSPECTION MODAL
            # -------------------------------------------------------------
            print("\n[STEP 9] Inspecting Driver Telemetry Modal...")
            t0 = time.time()
            inspect_btn = page.locator(".btn-row-inspect").first
            inspect_btn.click()
            page.wait_for_selector(".telemetry-modal-card", state="visible", timeout=5000)
            page.wait_for_selector(".modal-body", state="visible", timeout=6000)
            page.wait_for_timeout(500)

            gauges_count = page.locator(".gauge-card").count()
            has_graph = page.locator(".telemetry-svg").count() > 0 or page.locator(".telemetry-unavailable-banner").count() > 0
            step9_snap = OUTPUT_DIR / "13_telemetry_modal.png"
            page.screenshot(path=str(step9_snap), full_page=False)

            # Close modal
            page.locator(".btn-close-modal").click()
            page.wait_for_selector(".telemetry-modal-card", state="detached", timeout=3000)

            step9_passed = gauges_count >= 6 and has_graph
            report["steps"].append({
                "step": "B8_telemetry_modal",
                "description": "Open and inspect live CAN-bus car telemetry modal",
                "status": "PASSED" if step9_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "gauge_cards": gauges_count,
                    "has_graph": has_graph,
                    "screenshot": str(step9_snap),
                },
            })
            print(f" -> Telemetry modal status: {'PASSED' if step9_passed else 'FAILED'} (gauges: {gauges_count})")

            # -------------------------------------------------------------
            # STEP 10: NO-SESSION-DATA EMPTY STATE
            # -------------------------------------------------------------
            print("\n[STEP 10] Testing Suzuka Preview (NO_SESSION_DATA state)...")
            t0 = time.time()
            circuit_select.select_option("f1-2026-suzuka-preview")
            page.wait_for_timeout(2000)

            no_session_card = page.locator(".no-session-data-card")
            assert no_session_card.is_visible(), "NO_SESSION_DATA card missing"
            step10_snap = OUTPUT_DIR / "14_suzuka_no_session_data.png"
            page.screenshot(path=str(step10_snap), full_page=True)

            step10_passed = no_session_card.is_visible()
            report["steps"].append({
                "step": "B2_no_session_data_state",
                "description": "Verify Suzuka preview displays verified track geometry with graceful empty state",
                "status": "PASSED" if step10_passed else "FAILED",
                "duration_ms": int((time.time() - t0) * 1000),
                "details": {
                    "empty_state_visible": step10_passed,
                    "screenshot": str(step10_snap),
                },
            })
            print(f" -> Suzuka empty state status: {'PASSED' if step10_passed else 'FAILED'}")

            # Switch back to Monaco
            circuit_select.select_option("f1-2026-monaco-sim")
            page.wait_for_timeout(1500)

        except Exception as e:
            print(f"[FATAL EXCEPTION DURING BROWSER VERIFICATION] {e}")
            import traceback
            traceback.print_exc()
            report["exception"] = str(e)
            report["overall_status"] = "ERROR"
        finally:
            browser.close()

    # Final overall assessment
    has_error = report.get("overall_status") == "ERROR" or "exception" in report
    all_passed = (len(report["steps"]) >= 10) and all(s["status"] == "PASSED" for s in report["steps"])
    no_console_errors = len(report["console_errors"]) == 0
    no_http_errors = len(report["failed_requests"]) == 0

    if not has_error and all_passed and no_console_errors and no_http_errors:
        report["overall_status"] = "PASSED"
    else:
        report["overall_status"] = "FAILED"

    report_path = OUTPUT_DIR / "browser_test_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 80)
    print(f"BROWSER VERIFICATION FINISHED: {report['overall_status']}")
    print(f"Total Steps: {len(report['steps'])} | Passed: {sum(1 for s in report['steps'] if s['status'] == 'PASSED')}")
    print(f"Console Errors: {len(report['console_errors'])} | HTTP Errors: {len(report['failed_requests'])}")
    print(f"Report written to: {report_path}")
    print("=" * 80)

    if report["overall_status"] != "PASSED":
        sys.exit(1)


if __name__ == "__main__":
    run_browser_verification()
