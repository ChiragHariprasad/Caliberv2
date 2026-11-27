import os
import sys
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.abspath("screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def log(msg):
    print(msg, flush=True)

def safe_close_modals(page):
    try:
        # Close driver telemetry modal if open
        if page.locator(".modal-backdrop").count() > 0:
            close_btn = page.locator("button.btn-close-modal")
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"Notice: safe_close_modals backdrop: {e}")

    try:
        # Close evidence drawer if open
        if page.locator(".evidence-drawer-overlay").count() > 0:
            close_btn = page.locator("button.drawer-close-btn")
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"Notice: safe_close_modals evidence: {e}")

    try:
        # Close decision inspector if open
        if page.locator(".inspector-slideover-backdrop").count() > 0:
            close_btn = page.locator("button.btn-drawer-close")
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(500)
    except Exception as e:
        log(f"Notice: safe_close_modals inspector: {e}")

    try:
        # Close agent findings drawer if open
        findings_close = page.locator("div[style*='z-index: 1000'] button, div[style*='zIndex: 1000'] button")
        if findings_close.count() > 0 and findings_close.first.is_visible():
            findings_close.first.click()
            page.wait_for_timeout(500)
    except Exception as e:
        pass

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1.25,
        )
        page = context.new_page()

        log("Navigating to PULSE UI at http://127.0.0.1:5173...")
        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.wait_for_timeout(2500)

        # -------------------------------------------------------------
        # 01: Trackside Mission Control (Primary Overview)
        # -------------------------------------------------------------
        log("Capturing 01_trackside_mission_control.png...")
        page.click('button.nav-tab-btn:has-text("Trackside")')
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_trackside_mission_control.png"))

        # -------------------------------------------------------------
        # 02: Trackside Tactical Strategy & Pit Window Drawer
        # -------------------------------------------------------------
        log("Capturing 02_trackside_tactical_drawer.png...")
        tactical_header = page.locator(".tactical-drawer__header")
        if tactical_header.count() > 0:
            tactical_header.click()
            page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_trackside_tactical_drawer.png"))

        # -------------------------------------------------------------
        # 03: Live Tactical Consequence Feed & Momentum Chart (scroll down)
        # -------------------------------------------------------------
        log("Capturing 03_trackside_consequence_feed.png...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_trackside_consequence_feed.png"))
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(600)

        # -------------------------------------------------------------
        # 04: Driver CAN-Bus Telemetry Inspector Modal
        # -------------------------------------------------------------
        log("Capturing 04_driver_telemetry_modal.png...")
        participant_card = page.locator(".participant-card").first
        if participant_card.count() > 0:
            participant_card.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_driver_telemetry_modal.png"))
            # Explicitly close modal via button
            modal_close = page.locator("button.btn-close-modal")
            if modal_close.count() > 0 and modal_close.is_visible():
                modal_close.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        safe_close_modals(page)

        # -------------------------------------------------------------
        # 05: Tactical Evidence Provenance Drawer ("Why this?")
        # -------------------------------------------------------------
        log("Capturing 05_tactical_evidence_drawer.png...")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(800)
        evidence_btn = page.locator("button.evidence-trigger-btn").first
        if evidence_btn.count() > 0 and evidence_btn.is_visible():
            evidence_btn.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_tactical_evidence_drawer.png"))
            drawer_close = page.locator("button.drawer-close-btn")
            if drawer_close.count() > 0 and drawer_close.is_visible():
                drawer_close.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(1000)
        safe_close_modals(page)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(500)

        # -------------------------------------------------------------
        # 06: Integrity Board Matrix
        # -------------------------------------------------------------
        log("Capturing 06_integrity_board_matrix.png...")
        page.click('button.nav-tab-btn:has-text("Integrity Board")')
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "06_integrity_board_matrix.png"))

        # -------------------------------------------------------------
        # 07: Decision Inspector (Atoms & Provenance)
        # -------------------------------------------------------------
        log("Capturing 07_decision_inspector_atoms.png...")
        matrix_cell = page.locator("td.matrix-verdict-cell").first
        if matrix_cell.count() > 0:
            matrix_cell.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "07_decision_inspector_atoms.png"))

        # -------------------------------------------------------------
        # 08: Decision Inspector (Crypto Record & Revisions)
        # -------------------------------------------------------------
        log("Capturing 08_decision_inspector_crypto_revisions.png...")
        page.evaluate("""() => {
            const el = document.querySelector('.drawer-scroll-body');
            if (el) el.scrollTop = 550;
        }""")
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "08_decision_inspector_crypto_revisions.png"))
        
        # Close Decision Inspector
        inspector_close = page.locator("button.btn-drawer-close")
        if inspector_close.count() > 0 and inspector_close.is_visible():
            inspector_close.click()
        else:
            page.keyboard.press("Escape")
        page.wait_for_timeout(1000)
        safe_close_modals(page)

        # -------------------------------------------------------------
        # 09: SIA Logic Lab - Superposition View
        # -------------------------------------------------------------
        log("Capturing 09_sia_logic_lab_superposition.png...")
        page.click('button.nav-tab-btn:has-text("SIA Logic Lab")')
        page.wait_for_timeout(1500)
        page.click('button.workspace-tab-btn:has-text("State Envelope")')
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "09_sia_logic_lab_superposition.png"))

        # -------------------------------------------------------------
        # 10: SIA Logic Lab - Provenance & Entanglement Graph
        # -------------------------------------------------------------
        log("Capturing 10_sia_logic_lab_entanglement_graph.png...")
        page.click('button.workspace-tab-btn:has-text("Provenance")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "10_sia_logic_lab_entanglement_graph.png"))

        # -------------------------------------------------------------
        # 11: SIA Logic Lab - Contextuality DAG
        # -------------------------------------------------------------
        log("Capturing 11_sia_logic_lab_contextuality_dag.png...")
        page.click('button.workspace-tab-btn:has-text("Contextuality")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "11_sia_logic_lab_contextuality_dag.png"))

        # -------------------------------------------------------------
        # 12: SIA Logic Lab - State Algebra Evaluator
        # -------------------------------------------------------------
        log("Capturing 12_sia_logic_lab_state_algebra_tree.png...")
        page.click('button.workspace-tab-btn:has-text("Deterministic")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "12_sia_logic_lab_state_algebra_tree.png"))

        # -------------------------------------------------------------
        # 13: Agents & Pipeline - Runtime Diagnostics
        # -------------------------------------------------------------
        log("Capturing 13_agents_pipeline_runtime.png...")
        page.click('button.nav-tab-btn:has-text("Agents & Pipeline")')
        page.wait_for_timeout(1500)
        page.click('button.domain-tab:has-text("Orchestration & Runtime")')
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "13_agents_pipeline_runtime.png"))

        # -------------------------------------------------------------
        # 14: Agents & Pipeline - Agent Detail Findings Drawer
        # -------------------------------------------------------------
        log("Capturing 14_agents_pipeline_findings_drawer.png...")
        open_drawer_btn = page.locator("button:has-text('Open Drawer View')")
        if open_drawer_btn.count() > 0:
            open_drawer_btn.click()
            page.wait_for_timeout(1500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "14_agents_pipeline_findings_drawer.png"))
            close_drawer_btn = page.locator("button:has-text('Close [X]')")
            if close_drawer_btn.count() > 0:
                close_drawer_btn.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(800)
        safe_close_modals(page)

        # -------------------------------------------------------------
        # 15: Agents & Pipeline - Target Archetypes
        # -------------------------------------------------------------
        log("Capturing 15_agents_pipeline_target_archetypes.png...")
        page.click('button.domain-tab:has-text("Target Archetypes")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "15_agents_pipeline_target_archetypes.png"))

        # -------------------------------------------------------------
        # 16: Agents & Pipeline - Transport Diagnostics & Topology
        # -------------------------------------------------------------
        log("Capturing 16_agents_pipeline_topology.png...")
        page.click('button.domain-tab:has-text("Transport & Normalizer")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "16_agents_pipeline_topology.png"))

        # -------------------------------------------------------------
        # 17: Replay & Audit - Cryptographic Ledger Verifier
        # -------------------------------------------------------------
        log("Capturing 17_replay_audit_verifier.png...")
        page.click('button.nav-tab-btn:has-text("Replay & Audit")')
        page.wait_for_timeout(1500)
        page.click('button.domain-tab:has-text("Hash-Chain Ledger")')
        page.wait_for_timeout(1000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "17_replay_audit_verifier.png"))

        # -------------------------------------------------------------
        # 18: Replay & Audit - Bitemporal As-Of Query
        # -------------------------------------------------------------
        log("Capturing 18_replay_audit_as_of_query.png...")
        page.click('button.domain-tab:has-text("As-Of")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "18_replay_audit_as_of_query.png"))

        # -------------------------------------------------------------
        # 19: Replay & Audit - LAB Scenario Fault Injector
        # -------------------------------------------------------------
        log("Capturing 19_replay_audit_scenarios_lab.png...")
        page.click('button.domain-tab:has-text("LAB Scenario")')
        page.wait_for_timeout(1200)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "19_replay_audit_scenarios_lab.png"))

        # -------------------------------------------------------------
        # 20: Historical Controversy Corpus - Abu Dhabi 2021
        # -------------------------------------------------------------
        log("Capturing 20_historical_abu_dhabi_controversy.png...")
        page.select_option("#circuit-select", "f1-2021-abu-dhabi")
        page.wait_for_timeout(2000)
        page.click('button.nav-tab-btn:has-text("Trackside")')
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "20_historical_abu_dhabi_controversy.png"))

        # -------------------------------------------------------------
        # 21: Historical Controversy Corpus - Silverstone 2023
        # -------------------------------------------------------------
        log("Capturing 21_historical_silverstone_replay.png...")
        page.select_option("#circuit-select", "f1-2023-silverstone-race")
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "21_historical_silverstone_replay.png"))

        # -------------------------------------------------------------
        # 22: Homologated Preview & Empty State - Suzuka Preview
        # -------------------------------------------------------------
        log("Capturing 22_preview_suzuka_empty_state.png...")
        page.select_option("#circuit-select", "f1-2026-suzuka-preview")
        page.wait_for_timeout(2000)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "22_preview_suzuka_empty_state.png"))

        # Switch back to Monaco Sim for clean finish
        page.select_option("#circuit-select", "f1-2026-monaco-sim")
        page.wait_for_timeout(1000)

        browser.close()
        log("ALL_CAPTURES_COMPLETED_SUCCESSFULLY")

if __name__ == "__main__":
    run()
