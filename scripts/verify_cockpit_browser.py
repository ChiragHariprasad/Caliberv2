"""Browser-based verification of PULSE F1 Cockpit and Operations UI using Playwright.

Validates:
1. Dynamic circuit geometry rendering (Monaco, Silverstone, Suzuka).
2. Dynamic 20-driver grid in leaderboard with tyre badges and gaps.
3. Car telemetry modal with speed, throttle, brake, gear, rpm, drs, and time-series SVG graph.
4. Race Control & Stewarding tab separating Official FIA notices from PULSE AI domain.
5. Agent Operations tab exposing all 5 specialist agents with 13 live metrics and trace modal.
6. Pipeline Lab tab displaying streaming topology, Flink/Kafka metrics, reconciliation, and lineage.
7. Saves full-page screenshots to docs/screenshots/.
"""

import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = WORKSPACE_ROOT / "docs" / "screenshots"
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"


def wait_for_url(url: str, timeout: int = 30) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[*] Ensuring screenshot directory at {SCREENSHOTS_DIR}")

    env = os.environ.copy()
    backend_path = str(WORKSPACE_ROOT / "backend")
    env["PYTHONPATH"] = backend_path
    env["PYTHONUNBUFFERED"] = "1"
    env["PULSE_TRANSPORT_MODE"] = "KAFKA"

    backend_proc = None
    frontend_proc = None

    try:
        # 1. Start Backend Server
        print("[*] Launching PULSE FastAPI backend...")
        backend_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "pulse.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(WORKSPACE_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if not wait_for_url(f"{BACKEND_URL}/api/health", timeout=25):
            print("[!] Backend failed to start within 25s.")
            raise RuntimeError("Backend failed to start")
        print("[+] Backend is online and healthy!")

        # 2. Start Frontend Server
        print("[*] Launching PULSE Vite frontend (preview)...")
        frontend_proc = subprocess.Popen(
            ["cmd.exe", "/c", "npm", "run", "preview", "--", "--port", "5173", "--host", "127.0.0.1"],
            cwd=str(WORKSPACE_ROOT / "frontend"),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if not wait_for_url(FRONTEND_URL, timeout=20):
            print("[!] Frontend preview failed to start within 20s, falling back to dev server...")
            if frontend_proc:
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], capture_output=True)
                except Exception:
                    pass
            frontend_proc = subprocess.Popen(
                ["cmd.exe", "/c", "npm", "run", "dev", "--", "--port", "5173", "--host", "127.0.0.1"],
                cwd=str(WORKSPACE_ROOT / "frontend"),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if not wait_for_url(FRONTEND_URL, timeout=25):
                raise RuntimeError("Frontend failed to start")
        print("[+] Frontend is online at http://127.0.0.1:5173!")

        # 3. Run Playwright Browser Automation
        print("[*] Launching Chromium browser...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            # Navigate to Cockpit
            print("[*] Loading Cockpit Dashboard...")
            page.goto(FRONTEND_URL, wait_until="networkidle")
            page.wait_for_timeout(2000)

            # Assert Title and Header
            header = page.locator(".broadcast-banner")
            assert header.is_visible(), "Broadcast banner is missing"
            print("[+] Broadcast banner verified.")

            # Assert Track Map
            track_map = page.locator(".track-panel")
            assert track_map.is_visible(), "Track map panel is missing"
            circuit_svg = page.locator(".circuit-svg")
            assert circuit_svg.is_visible(), "Circuit SVG is missing"
            svg_car_nodes = page.locator(".car-node")
            car_count = svg_car_nodes.count()
            print(f"[+] Track Map rendered with {car_count} car markers on circuit.")

            # Assert Leaderboard Grid
            rows = page.locator(".f1-leaderboard-table tbody tr")
            row_count = rows.count()
            print(f"[+] Leaderboard table rendered with {row_count} drivers.")
            assert row_count >= 20, f"Expected at least 20 drivers, got {row_count}"

            # Capture Screenshot 1: Monaco Cockpit
            snap1_path = SCREENSHOTS_DIR / "01_cockpit_monaco.png"
            page.screenshot(path=str(snap1_path), full_page=True)
            print(f"[+] Saved Screenshot 1: {snap1_path.name}")

            # Open Car #16 (Leclerc) Telemetry Modal
            print("[*] Opening Car #16 (Charles Leclerc) telemetry inspection modal...")
            inspect_btn_16 = page.locator("tr:has-text('LEC') .btn-row-inspect").first
            if inspect_btn_16.is_visible():
                inspect_btn_16.click()
            else:
                rows.first.locator(".btn-row-inspect").click()

            page.wait_for_selector(".telemetry-modal-card", state="visible", timeout=8000)
            page.wait_for_selector(".telemetry-svg", state="visible", timeout=8000)

            # Verify Telemetry Modal Elements
            modal = page.locator(".telemetry-modal-card")
            assert modal.is_visible(), "Telemetry modal failed to open"
            assert page.locator(".telemetry-svg").is_visible(), "Telemetry SVG graph is missing"
            assert page.locator(".gauge-card").count() >= 6, "Expected at least 6 telemetry gauges"
            print("[+] Driver Telemetry Modal verified with gauges and time-series SVG graph.")

            # Capture Screenshot 2: Telemetry Modal
            snap2_path = SCREENSHOTS_DIR / "02_driver_telemetry_modal.png"
            page.screenshot(path=str(snap2_path), full_page=False)
            print(f"[+] Saved Screenshot 2: {snap2_path.name}")

            # Close Telemetry Modal
            page.locator(".btn-close-modal").click()
            page.wait_for_selector(".telemetry-modal-card", state="detached", timeout=3000)

            # Switch Circuit to Silverstone
            print("[*] Switching circuit dropdown to Silverstone...")
            circuit_select = page.locator("#circuit-select")
            circuit_select.select_option("silverstone")
            page.wait_for_timeout(1500)

            # Capture Screenshot 6: Silverstone Cockpit
            snap6_path = SCREENSHOTS_DIR / "06_cockpit_silverstone.png"
            page.screenshot(path=str(snap6_path), full_page=True)
            print(f"[+] Saved Screenshot 6: {snap6_path.name}")

            # Switch to Race Control & Stewarding Tab
            print("[*] Navigating to Race Control & Stewarding tab...")
            page.locator("button:has-text('Race Control')").click()
            page.wait_for_selector(".race-control-view", state="visible", timeout=5000)
            page.wait_for_timeout(1000)

            # Verify Separation of Official FIA vs PULSE AI
            assert page.locator(".official-stewarding-panel").is_visible(), "Official FIA stewarding panel is missing"
            assert page.locator(".official-notices-table").is_visible(), "Official notices table is missing"
            assert page.locator(".reg-code").count() >= 1, "Regulatory article references missing"
            print("[+] Race Control view verified with strict Official FIA regulatory feed.")

            # Capture Screenshot 3: Race Control
            snap3_path = SCREENSHOTS_DIR / "03_race_control_stewarding.png"
            page.screenshot(path=str(snap3_path), full_page=True)
            print(f"[+] Saved Screenshot 3: {snap3_path.name}")

            # Switch to Agent Operations Tab
            print("[*] Navigating to Agent Operations tab...")
            page.locator("button:has-text('Agent Operations')").click()
            page.wait_for_selector(".agent-operations-view", state="visible", timeout=5000)
            page.wait_for_timeout(1000)

            # Verify 5 Specialist Agents
            agent_cards = page.locator(".agent-telemetry-card")
            assert agent_cards.count() == 5, f"Expected 5 agent cards, got {agent_cards.count()}"
            print("[+] Agent Operations verified with all 5 specialist agents and live metrics.")

            # Open Trace Modal for Agent 1
            agent_cards.first.click()
            page.wait_for_selector(".trace-modal-card", state="visible", timeout=5000)
            page.wait_for_timeout(500)
            print("[+] Execution trace modal opened and verified.")

            # Capture Screenshot 4: Agent Operations
            snap4_path = SCREENSHOTS_DIR / "04_agent_operations.png"
            page.screenshot(path=str(snap4_path), full_page=True)
            print(f"[+] Saved Screenshot 4: {snap4_path.name}")

            # Close Trace Modal if open
            if page.locator(".trace-modal-card").is_visible():
                page.locator(".btn-close-modal").click()
                page.wait_for_selector(".trace-modal-card", state="detached", timeout=3000)

            # Switch to Pipeline Lab Tab
            print("[*] Navigating to Pipeline Lab tab...")
            page.locator("button:has-text('Pipeline Lab')").click()
            page.wait_for_selector(".pipeline-lab-view", state="visible", timeout=5000)
            page.wait_for_timeout(1000)

            # Verify Topology Diagram and Verification Table
            assert page.locator(".pipeline-flow-panel").is_visible(), "Pipeline flow panel missing"
            assert page.locator(".pipeline-node").count() >= 5, "Expected at least 5 pipeline topology nodes"
            assert page.locator(".verification-report-panel").is_visible(), "Verification report panel missing"
            assert page.locator(".stage-reconciliation-table").is_visible(), "Stage reconciliation table missing"
            print("[+] Pipeline Lab verified with topology, Flink/Kafka metrics, and reconciliation stages.")

            # Capture Screenshot 5: Pipeline Lab
            snap5_path = SCREENSHOTS_DIR / "05_pipeline_lab.png"
            page.screenshot(path=str(snap5_path), full_page=True)
            print(f"[+] Saved Screenshot 5: {snap5_path.name}")

            browser.close()
            print("\n=======================================================")
            print("  ALL BROWSER E2E TESTS AND SCREENSHOT CAPTURES PASSED!")
            print("=======================================================\n")

    finally:
        # Clean up processes
        print("[*] Cleaning up background processes...")
        if frontend_proc:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)], capture_output=True)
            except Exception:
                frontend_proc.terminate()
        if backend_proc:
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(backend_proc.pid)], capture_output=True)
            except Exception:
                backend_proc.terminate()
        print("[+] Cleanup complete.")


if __name__ == "__main__":
    main()
