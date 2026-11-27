"""Visual and Interactive Browser Verification for Integrity Board & SIA Logic Lab Redesign.
Runs in Playwright Chromium at 100% zoom across multiple viewports:
- 1920x1080 (Full HD desktop)
- 1480x900 (Medium laptop)
- 1280x800 (Compact desktop)
"""
import os
import shutil
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(r"C:\Users\chira\.gemini\antigravity\brain\9bf23c90-aac3-4e50-bc55-cbc23ba74104")
SHOTS_DIR = ARTIFACT_DIR / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

RESULTS = []

def record(msg: str):
    print(f"[VERIFY] {msg}", flush=True)
    RESULTS.append(msg)

def capture(page, name: str, full_page: bool = False):
    p1 = SHOTS_DIR / name
    p2 = ARTIFACT_DIR / name
    page.screenshot(path=str(p1), full_page=full_page)
    shutil.copyfile(p1, p2)
    record(f"Saved screenshot: {name}")

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ---------------------------------------------------------------------
        # TEST 1: 1920x1080 - INTEGRITY BOARD
        # ---------------------------------------------------------------------
        context = browser.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1.0)
        page = context.new_page()

        record("Loading app at http://localhost:5173/ ...")
        page.goto("http://localhost:5173/", wait_until="networkidle")
        time.sleep(2)

        # Navigate to Integrity Board
        record("Navigating to Integrity Board...")
        page.click("button:has-text('Integrity Board')")
        time.sleep(1.5)

        capture(page, "20_integrity_board_1920x1080.png")

        # Test Filter Toolbar: Select Team
        team_select = page.locator("#team-select").first
        if team_select.is_visible():
            team_select.select_option(index=1)
            time.sleep(0.5)
            record("Filtered by first team in dropdown")
            capture(page, "21_integrity_filtered_team.png")

            # Reset filters
            reset_btn = page.locator(".filter-reset-button").first
            if reset_btn.is_visible():
                reset_btn.click()
                time.sleep(0.5)
                record("Reset filters back to all")

        # Test Cell Hover Tooltip
        first_cell = page.locator("td.matrix-verdict-cell[role='button']").first
        if first_cell.is_visible():
            first_cell.hover()
            time.sleep(0.6)
            capture(page, "22_integrity_hover_tooltip.png")

        # Test Decision Inspector Drawer: click first cell
        if first_cell.is_visible():
            first_cell.click()
            time.sleep(1.0)
            record("Opened Decision Inspector Drawer")
            capture(page, "23_decision_inspector_open.png")

            # Scroll drawer to view evidence atoms and provenance
            drawer_body = page.locator(".drawer-scroll-body")
            if drawer_body.is_visible():
                drawer_body.evaluate("el => el.scrollTop = 400")
                time.sleep(0.5)
                capture(page, "24_decision_inspector_evidence_crypto.png")

                drawer_body.evaluate("el => el.scrollTop = 900")
                time.sleep(0.5)
                capture(page, "25_decision_inspector_timeline_limitations.png")

            # Close drawer
            close_btn = page.locator(".btn-drawer-close").first
            if close_btn.is_visible():
                close_btn.click()
                time.sleep(0.5)
                record("Closed Decision Inspector Drawer")

        # ---------------------------------------------------------------------
        # TEST 2: 1920x1080 - SIA LOGIC LAB WORKBENCH
        # ---------------------------------------------------------------------
        record("Navigating to SIA Logic Lab...")
        page.click("button:has-text('SIA Logic Lab')")
        time.sleep(1.5)

        # Tab 1: State Envelope & Superposition
        record("Testing SIA Logic Lab - Tab 1: State Envelope & Superposition")
        capture(page, "26_logic_lab_tab1_superposition.png")

        # Tab 2: Provenance & Entanglement Graph
        record("Testing SIA Logic Lab - Tab 2: Provenance & Entanglement Graph")
        page.click("button:has-text('Provenance & Entanglement')")
        time.sleep(1.0)
        capture(page, "27_logic_lab_tab2_provenance.png")

        # Test Axis Toggle: click Processing Origin Axis
        proc_btn = page.locator("button:has-text('Processing Origin Axis')").first
        if proc_btn.is_visible():
            proc_btn.click()
            time.sleep(0.5)
            record("Switched to Processing Origin Axis")
            capture(page, "28_logic_lab_tab2_processing_axis.png")

        # Tab 3: Contextuality & Scope Isolation
        record("Testing SIA Logic Lab - Tab 3: Contextuality & Scope Isolation")
        page.click("button:has-text('Contextuality & Scope')")
        time.sleep(1.0)
        capture(page, "29_logic_lab_tab3_contextuality.png")

        # Test selecting different evidence atom in Tab 3
        second_pill = page.locator(".atom-select-pill").nth(1)
        if second_pill.is_visible():
            second_pill.click()
            time.sleep(0.5)
            record("Selected second atom in Contextuality explorer")
            capture(page, "30_logic_lab_tab3_selected_atom.png")

        # Tab 4: Deterministic SIA Evaluator
        record("Testing SIA Logic Lab - Tab 4: Deterministic SIA Evaluator")
        page.click("button:has-text('Deterministic SIA Evaluator')")
        time.sleep(1.0)
        capture(page, "31_logic_lab_tab4_evaluator.png")

        # Test changing operator to Join (∨)
        join_btn = page.locator(".op-btn:has-text('Join')").first
        if join_btn.is_visible():
            join_btn.click()
            time.sleep(0.5)
            record("Switched evaluator operator to Join (∨)")

        # Test changing role rank
        suspect_chip = page.locator(".role-select-chip:has-text('SUS')").first
        if suspect_chip.is_visible():
            suspect_chip.click()
            time.sleep(0.5)
            record("Changed primary role to SUSPECT")

        capture(page, "32_logic_lab_tab4_evaluated_result.png")

        context.close()

        # ---------------------------------------------------------------------
        # TEST 3: MEDIUM LAPTOP (1480x900) AT 100% ZOOM
        # ---------------------------------------------------------------------
        context_med = browser.new_context(viewport={"width": 1480, "height": 900}, device_scale_factor=1.0)
        page_med = context_med.new_page()
        page_med.goto("http://localhost:5173/", wait_until="networkidle")
        time.sleep(1.5)

        page_med.click("button:has-text('Integrity Board')")
        time.sleep(1.0)
        capture(page_med, "33_integrity_board_1480x900.png")

        page_med.click("button:has-text('SIA Logic Lab')")
        time.sleep(1.0)
        capture(page_med, "34_logic_lab_tab1_1480x900.png")
        context_med.close()

        # ---------------------------------------------------------------------
        # TEST 4: COMPACT DESKTOP (1280x800) AT 100% ZOOM
        # ---------------------------------------------------------------------
        context_cpt = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1.0)
        page_cpt = context_cpt.new_page()
        page_cpt.goto("http://localhost:5173/", wait_until="networkidle")
        time.sleep(1.5)

        page_cpt.click("button:has-text('Integrity Board')")
        time.sleep(1.0)
        capture(page_cpt, "35_integrity_board_1280x800.png")

        page_cpt.click("button:has-text('SIA Logic Lab')")
        time.sleep(1.0)
        capture(page_cpt, "36_logic_lab_tab1_1280x800.png")
        context_cpt.close()

        browser.close()

    record("Visual & interactive browser verification completed successfully!")

if __name__ == "__main__":
    run_tests()
