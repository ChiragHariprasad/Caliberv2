import re
from pathlib import Path

styles_path = Path(r"e:\Caliberv2\frontend\src\styles.css")
content = styles_path.read_text(encoding="utf-8")

start_marker = "/* --- Integrity Matrix --- */"
end_marker = "/* --- Agents & Pipeline View --- */"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found! start_idx={start_idx}, end_idx={end_idx}")
    exit(1)

new_css = """/* ==========================================================================
   PULSE REDESIGN CORRECTION — INTEGRITY BOARD & SIA LOGIC LAB WORKBENCH
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. INTEGRITY BOARD (Session Evidence Integrity)
   -------------------------------------------------------------------------- */

.integrity-board-root {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.integrity-page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  gap: 24px;
}

.header-left-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.header-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--f1-red);
  font-family: var(--font-mono);
}

.header-title {
  font-size: 1.45rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.02em;
  margin: 0;
}

.header-subtitle {
  font-size: 0.82rem;
  color: var(--text-dim);
  margin-top: 2px;
  line-height: 1.4;
}

.header-right-group {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.header-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  font-weight: 600;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--f1-blue);
}

.streaming-status-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  font-weight: 700;
  border-radius: 6px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
  color: #34d399;
}

.streaming-pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
  animation: pulseGreenGlow 1.8s infinite;
}

@keyframes pulseGreenGlow {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

/* KPI Summary Strip */
.integrity-kpi-strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
  width: 100%;
}

@media (max-width: 1200px) {
  .integrity-kpi-strip {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .integrity-kpi-strip {
    grid-template-columns: repeat(2, 1fr);
  }
}

.kpi-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 18px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
  user-select: none;
}

.kpi-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.kpi-card.is-active {
  border-color: var(--f1-blue);
  box-shadow: 0 0 0 1px var(--f1-blue), 0 4px 12px rgba(59, 130, 246, 0.15);
  background: #101724;
}

.kpi-card-inner {
  display: flex;
  flex-direction: column;
}

.kpi-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.kpi-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
}

.kpi-state-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.kpi-card.kpi-total .kpi-state-dot { background: #60a5fa; }
.kpi-card.kpi-healthy .kpi-state-dot { background: #10b981; }
.kpi-card.kpi-suspect .kpi-state-dot { background: #f59e0b; }
.kpi-card.kpi-unknown .kpi-state-dot { background: #94a3b8; }
.kpi-card.kpi-degraded .kpi-state-dot { background: #ef4444; }
.kpi-card.kpi-voided .kpi-state-dot { background: #a855f7; }

.kpi-val {
  font-size: 1.75rem;
  font-weight: 800;
  font-family: var(--font-mono);
  color: #ffffff;
  line-height: 1;
  margin-bottom: 8px;
}

.kpi-pct-bar {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.kpi-pct-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.kpi-card.kpi-total .kpi-pct-fill { background: #3b82f6; }
.kpi-card.kpi-healthy .kpi-pct-fill { background: #10b981; }
.kpi-card.kpi-suspect .kpi-pct-fill { background: #f59e0b; }
.kpi-card.kpi-unknown .kpi-pct-fill { background: #94a3b8; }
.kpi-card.kpi-degraded .kpi-pct-fill { background: #ef4444; }
.kpi-card.kpi-voided .kpi-pct-fill { background: #a855f7; }

/* Filter Toolbar */
.integrity-filter-toolbar {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.filter-inputs-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  flex: 1;
}

.filter-field-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-field-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  font-weight: 700;
  text-transform: uppercase;
}

.filter-select, .filter-search-input {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px 10px;
  color: #ffffff;
  font-size: 0.78rem;
  outline: none;
  transition: border-color 0.15s ease;
}

.filter-select:focus, .filter-search-input:focus {
  border-color: var(--f1-blue);
}

.filter-search-input {
  min-width: 180px;
}

.filter-reset-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-dim);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.72rem;
  cursor: pointer;
  font-family: var(--font-mono);
  transition: all 0.15s ease;
}

.filter-reset-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.filter-active-count {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  font-weight: 600;
}

/* Integrity Matrix Data Table */
.integrity-matrix-container {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
  width: 100%;
}

.integrity-data-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  text-align: left;
}

.integrity-data-table th {
  background: #0d131d;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border-subtle);
  position: sticky;
  top: 0;
  z-index: 5;
}

.col-driver-header {
  width: 240px;
  min-width: 220px;
  position: sticky;
  left: 0;
  z-index: 6;
  background: #0d131d;
  border-right: 1px solid var(--border-subtle);
}

.col-contract-header {
  min-width: 150px;
}

.contract-code {
  font-size: 0.78rem;
  font-weight: 800;
  color: #ffffff;
}

.contract-name {
  font-size: 0.68rem;
  color: var(--text-dim);
  font-weight: 500;
  margin-top: 2px;
  white-space: nowrap;
}

.matrix-row {
  transition: background 0.12s ease;
}

.matrix-row:hover {
  background: #131a26;
}

.matrix-cell-driver {
  position: sticky;
  left: 0;
  z-index: 4;
  background: var(--bg-card);
  border-right: 1px solid var(--border-subtle);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  padding: 10px 16px;
}

.matrix-row:hover .matrix-cell-driver {
  background: #131a26;
}

.driver-ident-stack {
  display: flex;
  align-items: center;
  gap: 10px;
}

.driver-num-badge {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 800;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: #ffffff;
  flex-shrink: 0;
}

.driver-meta-box {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.driver-name-text {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.driver-team-tag {
  font-size: 0.68rem;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.matrix-cell-verdict {
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  border-right: 1px solid rgba(255, 255, 255, 0.02);
  padding: 6px;
  text-align: center;
}

.cell-verdict-button {
  width: 100%;
  padding: 7px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  transition: all 0.12s ease;
}

.cell-verdict-button:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.12);
}

.cell-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.badge-healthy {
  background: rgba(16, 185, 129, 0.12);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge-suspect {
  background: rgba(245, 158, 11, 0.12);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.3);
}

.badge-unknown {
  background: rgba(148, 163, 184, 0.12);
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.3);
}

.badge-degraded {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.badge-voided {
  background: rgba(168, 85, 247, 0.12);
  color: #c084fc;
  border: 1px solid rgba(168, 85, 247, 0.3);
}

.cell-alert-indicator {
  display: flex;
  align-items: center;
}

.cell-alert-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.cell-alert-dot.alert-suspect {
  background: #f59e0b;
  box-shadow: 0 0 6px #f59e0b;
}

.cell-alert-dot.alert-degraded {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
}

.matrix-empty-cell {
  color: rgba(255, 255, 255, 0.18);
  font-family: var(--font-mono);
  font-size: 0.72rem;
}

/* Hover Tooltip */
.matrix-hover-tooltip {
  position: fixed;
  z-index: 1000;
  background: #0b0f17;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
  border-radius: 6px;
  padding: 12px 14px;
  pointer-events: none;
  max-width: 320px;
  font-size: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  padding-bottom: 6px;
}

.tooltip-contract-code {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #ffffff;
}

.tooltip-reason {
  color: var(--text-muted);
  line-height: 1.35;
  font-size: 0.73rem;
}

.tooltip-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  background: rgba(255, 255, 255, 0.03);
  padding: 6px 8px;
  border-radius: 4px;
}

.tooltip-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tooltip-meta-k {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.tooltip-meta-v {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  font-weight: 600;
  color: #ffffff;
}

.tooltip-click-hint {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--f1-blue);
  text-align: right;
  margin-top: 2px;
}

/* Matrix Footer */
.integrity-matrix-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-top: 1px solid var(--border-subtle);
  background: var(--bg-card-subtle);
  font-size: 0.72rem;
  color: var(--text-dim);
}

.footer-legend {
  display: flex;
  align-items: center;
  gap: 14px;
}

.legend-title {
  font-family: var(--font-mono);
  font-weight: 700;
  text-transform: uppercase;
  font-size: 0.68rem;
  color: var(--text-dim);
}

.legend-items {
  display: flex;
  align-items: center;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-swatch {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.legend-swatch.swatch-healthy { background: #10b981; }
.legend-swatch.swatch-suspect { background: #f59e0b; }
.legend-swatch.swatch-unknown { background: #94a3b8; }
.legend-swatch.swatch-degraded { background: #ef4444; }
.legend-swatch.swatch-voided { background: #a855f7; }

.footer-meta {
  font-family: var(--font-mono);
  color: var(--text-dim);
}

/* --------------------------------------------------------------------------
   2. DECISION INSPECTOR (Slide-Over Right Drawer)
   -------------------------------------------------------------------------- */

.inspector-slideover-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(2px);
  z-index: 998;
}

.inspector-slideover-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: min(520px, 94vw);
  background: #0d131d;
  border-left: 1px solid var(--border-subtle);
  box-shadow: -10px 0 35px rgba(0, 0, 0, 0.85);
  z-index: 999;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.drawer-header-strip {
  padding: 18px 24px;
  border-bottom: 1px solid var(--border-subtle);
  background: #101724;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.drawer-eyebrow-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--f1-red);
  font-family: var(--font-mono);
}

.drawer-close-btn {
  background: transparent;
  border: none;
  color: var(--text-dim);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  line-height: 1;
}

.drawer-close-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.drawer-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.drawer-title {
  font-size: 1.25rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0;
}

.drawer-contract-badge {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.12);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.drawer-scroll-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.drawer-section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.section-badge-icon {
  font-size: 0.85rem;
}

.verdict-summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.summary-metric-cell {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.metric-value {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
  font-family: var(--font-mono);
}

.verdict-badge-lg {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 800;
  font-family: var(--font-mono);
  text-transform: uppercase;
}

.evaluator-explanation-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
}

.box-title {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
  margin-bottom: 4px;
}

.box-text {
  font-size: 0.78rem;
  color: #e2e8f0;
  line-height: 1.4;
}

/* Evidence Atoms Stack */
.evidence-atoms-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.evidence-atom-card {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.atom-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.atom-role-tag {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.06);
  color: #ffffff;
}

.atom-code-name {
  font-size: 0.78rem;
  font-weight: 700;
  color: #ffffff;
}

.atom-status-badge {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
}

.atom-details-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  background: rgba(255, 255, 255, 0.02);
  padding: 6px 8px;
  border-radius: 4px;
}

.atom-detail-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.atom-detail-col .lbl {
  font-size: 0.62rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.atom-detail-col .val {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 600;
}

.atom-hash-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.mono-hash {
  font-family: var(--font-mono);
  color: #94a3b8;
}

/* Provenance Card */
.provenance-detail-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.provenance-metric-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.common-cause-meter {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meter-bar-track {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.meter-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: #3b82f6;
  transition: width 0.3s ease;
}

.closure-deps-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.closure-dep-pill {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  padding: 3px 8px;
  border-radius: 4px;
  color: #cbd5e1;
}

/* Cryptographic Records */
.crypto-records-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.crypto-hash-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.crypto-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crypto-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.crypto-val-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px 10px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #94a3b8;
}

.copy-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-dim);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 0.65rem;
  cursor: pointer;
  transition: all 0.12s ease;
}

.copy-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

/* Revision Timeline */
.revision-timeline-v2 {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
  padding-left: 14px;
}

.timeline-node {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-marker {
  position: absolute;
  left: -14px;
  top: 4px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--f1-blue);
}

.node-content-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-top-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-time {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.node-verdict-tag {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
}

.node-reason {
  font-size: 0.74rem;
  color: #cbd5e1;
}

/* Limitations */
.limitations-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.limitation-alert-box {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.25);
  border-radius: 6px;
  padding: 10px 12px;
}

.limitation-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: #fbbf24;
  margin-bottom: 2px;
}

.limitation-text {
  font-size: 0.74rem;
  color: #e2e8f0;
  line-height: 1.35;
}

/* --------------------------------------------------------------------------
   3. SIA LOGIC LAB WORKBENCH (Master View)
   -------------------------------------------------------------------------- */

.logic-lab-workbench-root {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.logic-lab-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  gap: 20px;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-verdict-badge {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 800;
  padding: 3px 8px;
  border-radius: 4px;
  text-transform: uppercase;
}

/* Context Bar */
.logic-lab-context-bar {
  background: #0d131d;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 20px;
  width: 100%;
}

.context-items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  align-items: center;
}

.context-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.context-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
}

.context-val {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
}

.context-select {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 8px;
  color: #ffffff;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  outline: none;
}

.context-select:focus {
  border-color: var(--f1-blue);
}

/* Tab Navigation */
.logic-lab-tabs-nav {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  width: 100%;
}

@media (max-width: 992px) {
  .logic-lab-tabs-nav {
    grid-template-columns: repeat(2, 1fr);
  }
}

.lab-nav-tab {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 16px;
  text-align: left;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.lab-nav-tab:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: #121824;
}

.lab-nav-tab.is-active {
  background: #141d2e;
  border-color: var(--f1-blue);
  box-shadow: 0 0 0 1px var(--f1-blue);
}

.tab-number-badge {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--f1-blue);
  text-transform: uppercase;
}

.tab-title-text {
  font-size: 0.88rem;
  font-weight: 700;
  color: #ffffff;
}

.tab-desc-text {
  font-size: 0.72rem;
  color: var(--text-dim);
  line-height: 1.3;
}

.logic-lab-workspace-content {
  min-height: 600px;
  width: 100%;
}

/* --------------------------------------------------------------------------
   4. WORKSPACE 1: STATE ENVELOPE & SUPERPOSITION
   -------------------------------------------------------------------------- */

.state-envelope-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.workspace-section-header {
  margin-bottom: 4px;
}

.section-eyebrow {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--f1-blue);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.section-title {
  font-size: 1.2rem;
  font-weight: 800;
  color: #ffffff;
  margin: 2px 0 4px 0;
}

.section-desc {
  font-size: 0.78rem;
  color: var(--text-dim);
  line-height: 1.4;
}

.lattice-nodes-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  width: 100%;
}

@media (max-width: 900px) {
  .lattice-nodes-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.lattice-state-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  position: relative;
  transition: all 0.15s ease;
}

.lattice-state-card.is-active {
  border-color: #3b82f6;
  background: #111a2b;
  box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
}

.card-rank-tag {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
}

.card-title {
  font-size: 1rem;
  font-weight: 800;
  color: #ffffff;
}

.card-code {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: #94a3b8;
}

.card-desc {
  font-size: 0.74rem;
  color: var(--text-dim);
  line-height: 1.35;
}

.card-evidence-role {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  padding: 4px 8px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 4px;
  margin-top: auto;
}

/* Range Bar */
.envelope-range-bar-wrapper {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.range-bar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.range-title {
  font-size: 0.88rem;
  font-weight: 800;
  color: #ffffff;
}

.range-sub {
  font-size: 0.74rem;
  color: var(--text-dim);
}

.range-graphic-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 0;
}

.range-track {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  height: 24px;
  border-radius: 6px;
  overflow: hidden;
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
}

.range-segment {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  transition: all 0.2s ease;
  opacity: 0.25;
}

.range-segment.is-active-range {
  opacity: 1;
}

.range-segment.seg-degraded { background: rgba(239, 68, 68, 0.25); color: #f87171; }
.range-segment.seg-unknown { background: rgba(148, 163, 184, 0.25); color: #cbd5e1; }
.range-segment.seg-suspect { background: rgba(245, 158, 11, 0.25); color: #fbbf24; }
.range-segment.seg-healthy { background: rgba(16, 185, 129, 0.25); color: #34d399; }

.envelope-workbench-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 900px) {
  .envelope-workbench-two-col {
    grid-template-columns: 1fr;
  }
}

.evidence-slots-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.74rem;
}

.evidence-slots-table th {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-dim);
  font-family: var(--font-mono);
  font-size: 0.68rem;
}

.evidence-slots-table td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.reduction-rules-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.rule-card {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rule-formula {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: #60a5fa;
}

.rule-explanation {
  font-size: 0.72rem;
  color: var(--text-dim);
}

/* --------------------------------------------------------------------------
   5. WORKSPACE 2: DEPENDENCY & PROVENANCE GRAPH
   -------------------------------------------------------------------------- */

.provenance-graph-workspace {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.provenance-three-zone-grid {
  display: grid;
  grid-template-columns: 280px 1fr 320px;
  gap: 16px;
  min-height: 640px;
  width: 100%;
}

@media (max-width: 1200px) {
  .provenance-three-zone-grid {
    grid-template-columns: 260px 1fr;
  }
  .zone-inspector-column {
    grid-column: span 2;
  }
}

.zone-controls-column, .zone-inspector-column {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.zone-panel-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.zone-panel-title {
  font-size: 0.82rem;
  font-weight: 800;
  color: #ffffff;
}

.zone-panel-sub {
  font-size: 0.68rem;
  color: var(--text-dim);
}

.provenance-mode-toggle {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  background: #0b0f17;
  padding: 4px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
}

.mode-toggle-btn {
  background: transparent;
  border: none;
  padding: 6px 8px;
  font-size: 0.7rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.12s ease;
}

.mode-toggle-btn.is-active {
  background: #1e293b;
  color: #ffffff;
}

.sources-list-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  max-height: 480px;
}

.source-item-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.12s ease;
}

.source-item-card:hover {
  background: rgba(255, 255, 255, 0.04);
}

.source-item-card.is-selected {
  border-color: var(--f1-blue);
  background: rgba(59, 130, 246, 0.1);
}

.source-id-text {
  font-size: 0.78rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
}

.source-deps-count {
  font-size: 0.65rem;
  color: var(--text-dim);
  font-family: var(--font-mono);
}

.zone-graph-centre {
  background: #090d14;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.graph-canvas-wrapper {
  flex: 1;
  width: 100%;
  position: relative;
  overflow: hidden;
}

.graph-svg-canvas {
  width: 100%;
  height: 100%;
  min-height: 540px;
}

.graph-toolbar {
  position: absolute;
  top: 14px;
  right: 14px;
  display: flex;
  gap: 6px;
  background: rgba(11, 15, 23, 0.85);
  backdrop-filter: blur(4px);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 4px;
}

.graph-tool-btn {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #ffffff;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}

.graph-tool-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.graph-legend-strip {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  background: #0d131d;
  border-top: 1px solid var(--border-subtle);
  font-size: 0.7rem;
  color: var(--text-dim);
}

.legend-node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 4px;
}

/* Zone Inspector Column */
.node-inspector-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.inspector-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.inspector-node-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
}

.inspector-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: rgba(0, 0, 0, 0.25);
  padding: 8px;
  border-radius: 6px;
}

.inspector-common-cause-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.exposure-score-display {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.closure-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

/* --------------------------------------------------------------------------
   6. WORKSPACE 3: CONTEXTUALITY & SCOPE ISOLATION
   -------------------------------------------------------------------------- */

.contextuality-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.atom-selector-bar {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 18px;
  display: flex;
  align-items: center;
  gap: 14px;
}

.selector-title {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
}

.atom-pills-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.atom-select-pill {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 0.74rem;
  font-family: var(--font-mono);
  color: #cbd5e1;
  cursor: pointer;
  transition: all 0.12s ease;
}

.atom-select-pill:hover {
  background: rgba(255, 255, 255, 0.05);
}

.atom-select-pill.is-active {
  background: rgba(59, 130, 246, 0.15);
  border-color: var(--f1-blue);
  color: #60a5fa;
  font-weight: 700;
}

.atom-metadata-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  background: #0d131d;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 12px 18px;
}

.atom-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-lbl {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.meta-val {
  font-size: 0.78rem;
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 600;
}

.branching-diagram-container {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.branching-diagram-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.branching-diagram-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
}

.branching-svg-wrapper {
  width: 100%;
  min-height: 280px;
  background: #090d14;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
  overflow: hidden;
}

.contract-cards-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 900px) {
  .contract-cards-grid {
    grid-template-columns: 1fr;
  }
}

.contract-eval-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.contract-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.contract-dep-atoms-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.contract-isolation-proof {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  padding: 6px 10px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 4px;
  color: #a7f3d0;
  margin-top: auto;
}

/* --------------------------------------------------------------------------
   7. WORKSPACE 4: DETERMINISTIC SIA EVALUATOR
   -------------------------------------------------------------------------- */

.evaluator-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.algebra-ranks-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

@media (max-width: 800px) {
  .algebra-ranks-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.rank-hierarchy-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rank-num {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
}

.rank-name {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
}

.rank-condition {
  font-size: 0.72rem;
  color: var(--text-dim);
}

.operator-bar {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .operator-bar {
    grid-template-columns: 1fr;
  }
}

.operator-btn {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 18px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  text-align: left;
  transition: all 0.15s ease;
}

.operator-btn:hover {
  background: #111a28;
  border-color: rgba(255, 255, 255, 0.2);
}

.operator-btn.is-active {
  background: #141d2e;
  border-color: var(--f1-blue);
  box-shadow: 0 0 0 1px var(--f1-blue);
}

.operator-math-symbol {
  font-size: 1.25rem;
  font-weight: 800;
  font-family: var(--font-mono);
  color: var(--f1-blue);
}

.operator-name {
  font-size: 0.88rem;
  font-weight: 800;
  color: #ffffff;
}

.operator-desc {
  font-size: 0.72rem;
  color: var(--text-dim);
  line-height: 1.35;
}

.input-roles-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

@media (max-width: 992px) {
  .input-roles-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.input-role-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.role-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.role-title {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
}

.role-weight-badge {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.role-rank-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.rank-select-btn {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px;
  font-size: 0.7rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.12s ease;
  text-align: center;
}

.rank-select-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.rank-select-btn.is-selected {
  background: rgba(59, 130, 246, 0.15);
  border-color: var(--f1-blue);
  color: #60a5fa;
  font-weight: 700;
}

.result-container-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-title {
  font-size: 1.05rem;
  font-weight: 800;
  color: #ffffff;
}

.result-badge-xl {
  font-family: var(--font-mono);
  font-size: 0.88rem;
  font-weight: 800;
  padding: 6px 14px;
  border-radius: 6px;
  text-transform: uppercase;
}

.result-trace-box {
  background: #090d14;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.trace-rule-code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #34d399;
  font-weight: 700;
}

.trace-explanation {
  font-size: 0.75rem;
  color: var(--text-dim);
}

"""

updated_content = content[:start_idx] + new_css + content[end_idx:]
styles_path.write_text(updated_content, encoding="utf-8")
print(f"Successfully replaced CSS from index {start_idx} to {end_idx}. New length: {len(updated_content)}")
