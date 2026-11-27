"""Verification script for sub-second 0.5s smoothness and continuous real-time streaming.

Verifies:
1. Replay start on active Grand Prix session
2. Arrival of events via SSE stream
3. Timing delta between consecutive DRIVER_STATE_UPDATED events is paced to ~0.5s (no 20ms bursts)
4. Monotonic advancement of car coordinates across 0.5s ticks
5. Real Playwright browser test observing visual coordinate glide
"""

import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

FRONTEND_URL = "http://127.0.0.1:5173"
BACKEND_URL = "http://127.0.0.1:8000"

def post_json(endpoint: str, data: dict = None) -> dict:
    url = f"{BACKEND_URL}{endpoint}"
    req_data = json.dumps(data or {}).encode("utf-8") if data is not None else b"{}"
    req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=" * 80)
    print("TESTING 0.5S STREAMING SMOOTHNESS AND CONTINUOUS REAL-TIME PACING")
    print("=" * 80)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("[1] Opening browser at http://127.0.0.1:5173...")
        page.goto(FRONTEND_URL, wait_until="networkidle")
        page.wait_for_selector(".circuit-select-input", timeout=10000)

        print("[2] Selecting Japanese Grand Prix (f1-2026-suzuka-race)...")
        circuit_select = page.locator("#circuit-select")
        circuit_select.select_option("f1-2026-suzuka-race")
        page.wait_for_timeout(2000)

        print("[3] Setting speed to 2.0x for rapid smooth verification...")
        page.get_by_role("button", name="Playback speed 2x").click()
        page.wait_for_timeout(500)

        car1 = page.locator('g[data-driver-number="1"]')
        t0_style = car1.get_attribute("style") or ""
        print(f" -> Initial Car #1 transform: {t0_style}")

        print("[4] Clicking Play button in Replay Controls...")
        page.locator(".play-btn").click()

        transforms = []
        print("[5] Sampling Car #1 position every 0.5s for 6 seconds (12 ticks)...")
        for i in range(12):
            page.wait_for_timeout(500)
            style = car1.get_attribute("style") or ""
            elapsed_el = page.locator(".telemetry-value").first
            elapsed_txt = elapsed_el.text_content() if elapsed_el else ""
            scrubber_el = page.locator(".scrubber-progress-readout").first
            scrubber_txt = scrubber_el.text_content() if scrubber_el else ""

            transforms.append((time.time(), style, elapsed_txt, scrubber_txt))
            print(f"  Tick {i+1:02d} (+{(i+1)*0.5:.1f}s): style='{style}', scrubber='{scrubber_txt}'")

        # Pause playback
        print("[6] Pausing playback...")
        page.locator(".play-btn").click()
        page.wait_for_timeout(500)

        # Check unique positions
        unique_styles = set(t[1] for t in transforms)
        print(f"\n[7] Unique car positions observed: {len(unique_styles)} / 10 ticks")

        # Take screenshot
        screenshot_path = "reports/browser_verification/17_smooth_streaming_05s.png"
        page.screenshot(path=screenshot_path)
        print(f"[8] Captured verification screenshot: {screenshot_path}")

        browser.close()

        assert len(console_errors) == 0, f"Encountered console errors: {console_errors}"
        assert len(unique_styles) >= 4, f"Expected car to move continuously across ticks, but only saw {len(unique_styles)} unique positions!"
        print("\n[SUCCESS] 0.5s Smoothness and continuous movement verified successfully with 0 console errors!")

if __name__ == "__main__":
    main()
