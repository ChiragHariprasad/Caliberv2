import re
from pathlib import Path

exact_css = """/* ==========================================================================
   PULSE REDESIGN CORRECTION — COMPREHENSIVE WORKBENCH STYLES
   Exact class mappings for Integrity Board & SIA Logic Lab Workspaces
   ========================================================================== */

/* --------------------------------------------------------------------------
   1. INTEGRITY BOARD (IntegrityMatrix.tsx)
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

.integrity-page-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.integrity-section-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--f1-red);
  font-family: var(--font-mono);
}

.eyebrow-accent-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--f1-red);
}

.integrity-main-heading {
  font-size: 1.5rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.02em;
  margin: 0;
}

.integrity-session-description {
  font-size: 0.82rem;
  color: var(--text-dim);
  margin-top: 2px;
  line-height: 1.4;
}

.integrity-page-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.header-meta-pill {
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

.header-meta-pill.streaming-status {
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.3);
  color: #34d399;
  font-weight: 700;
}

.pulse-indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
  animation: pulseGreenGlow 1.8s infinite;
}

.header-mode-toggle {
  display: flex;
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 2px;
}

.header-mode-toggle button {
  background: transparent;
  border: none;
  color: var(--text-dim);
  padding: 5px 10px;
  font-size: 0.7rem;
  font-family: var(--font-mono);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.12s ease;
}

.header-mode-toggle button.is-active {
  background: #1e293b;
  color: #ffffff;
  font-weight: 700;
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

.kpi-metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 18px;
  cursor: pointer;
  transition: all 0.15s ease;
  position: relative;
  overflow: hidden;
  user-select: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.kpi-metric-card:hover {
  border-color: rgba(255, 255, 255, 0.2);
  transform: translateY(-1px);
}

.kpi-metric-card.is-active-filter {
  border-color: var(--f1-blue);
  box-shadow: 0 0 0 1px var(--f1-blue), 0 4px 12px rgba(59, 130, 246, 0.15);
  background: #101724;
}

.kpi-metric-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.kpi-metric-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
}

.kpi-metric-value-box {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.kpi-metric-number {
  font-size: 1.75rem;
  font-weight: 800;
  font-family: var(--font-mono);
  color: #ffffff;
  line-height: 1;
}

.kpi-metric-subtext {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.kpi-metric-footer {
  width: 100%;
}

.kpi-metric-accent-line {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
  position: relative;
}

.kpi-metric-accent-line::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  width: var(--progress, 100%);
  background: #3b82f6;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.kpi-metric-card--healthy .kpi-metric-accent-line::after { background: #10b981; }
.kpi-metric-card--suspect .kpi-metric-accent-line::after { background: #f59e0b; }
.kpi-metric-card--unknown .kpi-metric-accent-line::after { background: #94a3b8; }
.kpi-metric-card--degraded .kpi-metric-accent-line::after { background: #ef4444; }
.kpi-metric-card--voided .kpi-metric-accent-line::after { background: #a855f7; }

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

.filter-toolbar-controls {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  flex: 1;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  font-weight: 700;
  text-transform: uppercase;
}

.filter-select {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px 10px;
  color: #ffffff;
  font-size: 0.78rem;
  outline: none;
  transition: border-color 0.15s ease;
  font-family: var(--font-mono);
}

.filter-select:focus {
  border-color: var(--f1-blue);
}

.filter-reset-button, .btn-clear-matrix-filters {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: var(--text-dim);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.72rem;
  cursor: pointer;
  font-family: var(--font-mono);
  transition: all 0.15s ease;
}

.filter-reset-button:hover, .btn-clear-matrix-filters:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.25);
}

.filter-toolbar-search {
  display: flex;
  align-items: center;
}

.search-bar-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-bar-icon {
  position: absolute;
  left: 10px;
  color: var(--text-dim);
  pointer-events: none;
}

.search-bar-input {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 6px 12px 6px 32px;
  color: #ffffff;
  font-size: 0.78rem;
  outline: none;
  width: 220px;
  transition: border-color 0.15s ease;
}

.search-bar-input:focus {
  border-color: var(--f1-blue);
}

.search-bar-clear {
  position: absolute;
  right: 8px;
  background: transparent;
  border: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 0.85rem;
}

/* Integrity Matrix Data Table */
.matrix-table-wrapper {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow-x: auto;
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

.th-participant-col {
  width: 260px;
  min-width: 240px;
  position: sticky;
  left: 0;
  z-index: 6;
  background: #0d131d;
  border-right: 1px solid var(--border-subtle);
}

.th-contract-col {
  min-width: 150px;
}

.contract-col-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.contract-col-name {
  font-size: 0.78rem;
  font-weight: 800;
  color: #ffffff;
}

.contract-col-scope {
  font-size: 0.65rem;
  color: var(--text-dim);
  font-weight: 500;
}

.matrix-data-row {
  transition: background 0.12s ease;
}

.matrix-data-row:hover {
  background: #131a26;
}

.matrix-data-row.is-filtered-out {
  opacity: 0.25;
}

.matrix-participant-cell {
  position: sticky;
  left: 0;
  z-index: 4;
  background: var(--bg-card);
  border-right: 1px solid var(--border-subtle);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  padding: 10px 16px;
}

.matrix-data-row:hover .matrix-participant-cell {
  background: #131a26;
}

.participant-ident-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}

.participant-badges {
  display: flex;
  align-items: center;
  gap: 4px;
}

.p-pos-badge {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--text-dim);
  width: 18px;
}

.p-num-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 800;
  padding: 3px 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  color: #ffffff;
}

.participant-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.p-driver-name {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.p-team-name {
  font-size: 0.68rem;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.matrix-verdict-cell {
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  border-right: 1px solid rgba(255, 255, 255, 0.02);
  padding: 4px;
  text-align: center;
}

.matrix-verdict-cell.is-alert-cell {
  background: rgba(239, 68, 68, 0.04);
}

.matrix-verdict-cell.is-selected-cell {
  background: rgba(59, 130, 246, 0.08);
  outline: 1px solid var(--f1-blue);
}

.cell-verdict-button {
  width: 100%;
  padding: 6px 8px;
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

.verdict-cell-content {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.verdict-pill-badge {
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

.alert-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
}

.matrix-empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  gap: 12px;
  color: var(--text-dim);
}

/* Hover Tooltip */
.matrix-hover-tooltip {
  position: fixed;
  z-index: 1000;
  background: #0b0f17;
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.85);
  border-radius: 6px;
  padding: 12px 14px;
  pointer-events: none;
  max-width: 320px;
  font-size: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tooltip-title {
  font-family: var(--font-mono);
  font-weight: 700;
  color: #ffffff;
  font-size: 0.78rem;
}

.tooltip-sub {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.35;
}

.tooltip-state {
  display: inline-block;
  margin-top: 2px;
}

.tooltip-hint {
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

.footer-left-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.footer-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
}

.footer-right-info {
  font-family: var(--font-mono);
  color: var(--text-dim);
}

/* --------------------------------------------------------------------------
   2. DECISION INSPECTOR (DecisionInspector.tsx)
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
  gap: 8px;
  flex-shrink: 0;
}

.drawer-header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.drawer-header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.drawer-instance-id {
  font-size: 1.15rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0;
  font-family: var(--font-mono);
}

.drawer-driver-subline {
  font-size: 0.78rem;
  color: var(--text-dim);
}

.drawer-meta-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.contract-badge, .revision-badge, .maturity-badge {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  color: #cbd5e1;
}

.drawer-badge-sep {
  color: rgba(255, 255, 255, 0.2);
}

.btn-drawer-close {
  background: transparent;
  border: none;
  color: var(--text-dim);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  line-height: 1;
}

.btn-drawer-close:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
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

.drawer-section-heading-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.drawer-section-heading {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.74rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.section-pill {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  background: rgba(255, 255, 255, 0.05);
  padding: 2px 6px;
  border-radius: 3px;
  color: var(--text-dim);
}

.verdict-summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.summary-field {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.field-value {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
  font-family: var(--font-mono);
}

.explanation-paragraph {
  font-size: 0.78rem;
  color: #e2e8f0;
  line-height: 1.45;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
  margin: 0;
}

/* Supporting Evidence Stack */
.evidence-roles-stack {
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

.atom-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.atom-role-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.atom-role-name code {
  font-size: 0.78rem;
  color: #ffffff;
  font-weight: 700;
}

.atom-kind-tag {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.atom-kind-tag.is-ref {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
}

.atom-kind-tag.is-evidence {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.atom-card-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  background: rgba(255, 255, 255, 0.02);
  padding: 8px 10px;
  border-radius: 4px;
}

.atom-grid-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.atom-item-label {
  font-size: 0.62rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.atom-item-val {
  font-size: 0.75rem;
  color: #ffffff;
  font-weight: 600;
}

.threshold-gauge-wrapper {
  margin-top: 4px;
}

/* Provenance Section */
.provenance-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.prov-label {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.exposure-meter-bar {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}

.exposure-meter-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.origin-pills-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.origin-pill {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-subtle);
  padding: 3px 8px;
  border-radius: 4px;
  color: #cbd5e1;
}

.origin-pill--source {
  border-color: rgba(59, 130, 246, 0.3);
  color: #93c5fd;
}

.origin-pill--proc {
  border-color: rgba(168, 85, 247, 0.3);
  color: #d8b4fe;
}

/* Cryptographic Records */
.crypto-hash-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.crypto-hash-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.crypto-hash-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.btn-copy-hash {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-dim);
  border-radius: 3px;
  padding: 2px 6px;
  font-size: 0.65rem;
  cursor: pointer;
  font-family: var(--font-mono);
  transition: all 0.12s ease;
}

.btn-copy-hash:hover {
  background: rgba(255, 255, 255, 0.08);
  color: #ffffff;
}

.crypto-hash-code {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px 10px;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #94a3b8;
  word-break: break-all;
}

.chain-verified-pill {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: #34d399;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.25);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* Timeline & Witnesses */
.timeline-entry {
  display: flex;
  gap: 12px;
  position: relative;
  padding-bottom: 12px;
}

.timeline-node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--f1-blue);
  margin-top: 4px;
  flex-shrink: 0;
}

.timeline-entry-body {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.timeline-entry-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timeline-rev-tag {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #ffffff;
}

.timeline-maturity {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.timeline-reason-text {
  font-size: 0.74rem;
  color: #cbd5e1;
}

.timeline-entry-hash {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: #94a3b8;
}

.witness-callout {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.witness-header-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.witness-code {
  font-size: 0.74rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: #ffffff;
}

.witness-role {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--f1-blue);
}

.witness-detail-text {
  font-size: 0.72rem;
  color: var(--text-dim);
}

.limitations-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.limitations-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: #fbbf24;
}

/* --------------------------------------------------------------------------
   3. SIA LOGIC LAB MASTER WORKBENCH (SiaLogicLabView.tsx)
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

.logic-lab-header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.logic-lab-eyebrow {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--f1-red);
}

.eyebrow-accent-square {
  width: 6px;
  height: 6px;
  background: var(--f1-red);
}

.logic-lab-main-heading {
  font-size: 1.5rem;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.02em;
  margin: 0;
}

.logic-lab-subheading {
  font-size: 0.82rem;
  color: var(--text-dim);
  margin-top: 2px;
  line-height: 1.4;
}

.logic-lab-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.evaluator-engine-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 6px;
}

.engine-name {
  font-size: 0.74rem;
  font-family: var(--font-mono);
  font-weight: 800;
  color: #34d399;
}

.pulse-green-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px #10b981;
}

.engine-regime {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

/* Context Bar */
.logic-lab-context-bar {
  background: #0d131d;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 14px 20px;
  width: 100%;
}

.context-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ctx-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-dim);
}

.ctx-val {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
}

.ctx-sub-code {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.ctx-decision-select {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 8px;
  color: #ffffff;
  font-size: 0.75rem;
  font-family: var(--font-mono);
  outline: none;
}

.ctx-decision-select:focus {
  border-color: var(--f1-blue);
}

.ctx-contract-badge {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 700;
  color: #60a5fa;
}

.ctx-slots-count, .ctx-maturity-tag {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: #cbd5e1;
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

.workspace-tab-btn {
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

.workspace-tab-btn:hover {
  border-color: rgba(255, 255, 255, 0.2);
  background: #121824;
}

.workspace-tab-btn.is-active-tab {
  background: #141d2e;
  border-color: var(--f1-blue);
  box-shadow: 0 0 0 1px var(--f1-blue);
}

.tab-step-num {
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
   4. WORKSPACE 1: STATE ENVELOPE (SuperpositionView.tsx)
   -------------------------------------------------------------------------- */

.state-envelope-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 100%;
}

.section-title-wrap {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
  margin-bottom: 12px;
}

.title-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.eyebrow-accent {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--f1-blue);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.workspace-section-title {
  font-size: 1.15rem;
  font-weight: 800;
  color: #ffffff;
  margin: 0;
}

.lattice-order-formula {
  font-size: 0.74rem;
  font-family: var(--font-mono);
  color: #94a3b8;
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
  gap: 10px;
  position: relative;
  transition: all 0.15s ease;
}

.lattice-state-card.is-in-envelope-range {
  border-color: rgba(59, 130, 246, 0.5);
  background: #111a2b;
}

.lattice-state-card.is-current-state {
  border-color: #3b82f6;
  box-shadow: 0 0 16px rgba(59, 130, 246, 0.25);
}

.state-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.state-card-rank-badge {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 800;
  color: var(--text-dim);
}

.state-card-envelope-tags {
  display: flex;
  gap: 4px;
}

.envelope-tag {
  font-size: 0.62rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.tag--lower { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.tag--upper { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
.tag--current { background: rgba(16, 185, 129, 0.2); color: #34d399; }
.tag--possible { background: rgba(255, 255, 255, 0.05); color: #94a3b8; }

.state-card-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.state-name-display {
  font-size: 1.05rem;
  font-weight: 800;
  color: #ffffff;
}

.state-meaning-text {
  font-size: 0.74rem;
  color: var(--text-dim);
  line-height: 1.35;
}

.state-conditions-box {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cond-label {
  font-size: 0.62rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.cond-text {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: #cbd5e1;
}

/* Range Bar */
.envelope-visual-section {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.range-bar-track {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  height: 28px;
  border-radius: 6px;
  overflow: hidden;
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
}

.range-bar-tick {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  opacity: 0.3;
  transition: all 0.2s ease;
}

.range-bar-tick.is-in-envelope-range {
  opacity: 1;
}

.range-bar-tick.is-current-tick {
  box-shadow: inset 0 0 0 2px var(--f1-blue);
}

.tick-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.range-bar-legend {
  display: flex;
  justify-content: space-between;
  font-size: 0.74rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

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

.envelope-roles-section, .envelope-explanation-section {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-slots-table-wrap {
  overflow-x: auto;
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
  text-align: left;
}

.evidence-slots-table td {
  padding: 8px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.slot-row.is-limiting-row {
  background: rgba(245, 158, 11, 0.04);
}

.limiting-impact-badge {
  color: #fbbf24;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
}

.resolved-impact-badge {
  color: #34d399;
  font-family: var(--font-mono);
  font-size: 0.68rem;
}

.role-kind-pill {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  padding: 2px 6px;
  border-radius: 3px;
}

.role-kind-pill.is-ref {
  background: rgba(168, 85, 247, 0.15);
  color: #c084fc;
}

.role-kind-pill.is-ev {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}

.slot-status-pill {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
}

.slot-status-pill.status--admitted { background: rgba(16, 185, 129, 0.15); color: #34d399; }
.slot-status-pill.status--pending { background: rgba(245, 158, 11, 0.15); color: #fbbf24; }
.slot-status-pill.status--missing { background: rgba(239, 68, 68, 0.15); color: #f87171; }
.slot-status-pill.status--rejected { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; }

.explanation-card-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-block {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.78rem;
  font-weight: 700;
  color: #ffffff;
}

.info-block p {
  font-size: 0.74rem;
  color: var(--text-dim);
  line-height: 1.4;
  margin: 0;
}

/* --------------------------------------------------------------------------
   5. WORKSPACE 2: DEPENDENCY & PROVENANCE GRAPH (EntanglementGraph.tsx)
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

.decision-brief-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brief-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.brief-id {
  font-size: 0.78rem;
  font-weight: 700;
  font-family: var(--font-mono);
  color: #ffffff;
}

.brief-stat-row {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
}

.brief-sub {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.axis-selector-box {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.axis-toggle-btn {
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px 10px;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  cursor: pointer;
  text-align: left;
  transition: all 0.12s ease;
}

.axis-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.04);
}

.axis-toggle-btn.is-active-axis {
  background: #1e293b;
  border-color: var(--f1-blue);
  color: #ffffff;
  font-weight: 700;
}

.nodes-list-scroll {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  max-height: 400px;
}

.node-list-item {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 8px 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.12s ease;
}

.node-list-item:hover {
  background: rgba(255, 255, 255, 0.04);
}

.node-list-item.is-selected-item {
  border-color: var(--f1-blue);
  background: rgba(59, 130, 246, 0.12);
}

.node-type-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.node-item-name {
  font-size: 0.74rem;
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 600;
}

.zone-graph-centre {
  background: #090d14;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.graph-canvas-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: #0d131d;
}

.canvas-title {
  font-size: 0.85rem;
  font-weight: 800;
  color: #ffffff;
}

.canvas-subtitle {
  font-size: 0.7rem;
  color: var(--text-dim);
}

.zoom-buttons-group {
  display: flex;
  gap: 6px;
}

.btn-zoom {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  color: #ffffff;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-zoom:hover {
  background: #1e293b;
}

.graph-canvas-wrapper {
  flex: 1;
  width: 100%;
  position: relative;
}

.provenance-svg-canvas {
  width: 100%;
  height: 100%;
  min-height: 520px;
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

.legend-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* Zone Inspector */
.ins-header-block {
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.ins-node-id {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
  font-family: var(--font-mono);
}

.ins-node-name {
  font-size: 0.75rem;
  color: var(--text-dim);
}

.ins-category-badge {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.05);
  color: #60a5fa;
  margin-top: 4px;
  display: inline-block;
}

.inspector-card-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ins-property-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.prop-header-row {
  display: flex;
  justify-content: space-between;
}

.prop-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.prop-val {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: #ffffff;
  font-weight: 700;
}

.prop-desc {
  font-size: 0.68rem;
  color: var(--text-dim);
}

.closure-tags-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.ins-rule-box {
  background: rgba(16, 185, 129, 0.06);
  border: 1px solid rgba(16, 185, 129, 0.25);
  border-radius: 4px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.rule-title {
  font-size: 0.72rem;
  font-weight: 700;
  color: #34d399;
}

.rule-text {
  font-size: 0.7rem;
  color: #cbd5e1;
  line-height: 1.35;
}

/* --------------------------------------------------------------------------
   6. WORKSPACE 3: CONTEXTUALITY (ContextualityDag.tsx)
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

.atom-sel-label {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
  text-transform: uppercase;
}

.atom-pills-group {
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
  display: flex;
  align-items: center;
  gap: 6px;
}

.atom-select-pill:hover {
  background: rgba(255, 255, 255, 0.05);
}

.atom-select-pill.is-selected-atom {
  background: rgba(59, 130, 246, 0.15);
  border-color: var(--f1-blue);
  color: #60a5fa;
  font-weight: 700;
}

.atom-pill-role {
  font-size: 0.65rem;
  color: var(--text-dim);
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

.meta-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.meta-k {
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

.contextuality-visual-centre {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.centre-title-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.centre-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
}

.centre-sub {
  font-size: 0.72rem;
  color: var(--text-dim);
}

.contracts-counter-pill {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  padding: 3px 8px;
  border-radius: 4px;
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

.contract-eval-card.is-selected-card {
  border-color: var(--f1-blue);
}

.eval-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  padding-bottom: 8px;
}

.eval-card-id {
  font-size: 0.78rem;
  font-weight: 800;
  color: #ffffff;
  font-family: var(--font-mono);
}

.eval-card-scope {
  font-size: 0.65rem;
  color: var(--text-dim);
  font-family: var(--font-mono);
}

.eval-card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.eval-constraints-box {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.constraints-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.eval-outcome-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.eval-explanation-text {
  font-size: 0.72rem;
  color: var(--text-dim);
  line-height: 1.35;
}

.isolation-guarantee {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  padding: 6px 10px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.2);
  border-radius: 4px;
  color: #a7f3d0;
  margin-top: auto;
}

.theorem-callout {
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.25);
  border-radius: 6px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.75rem;
  color: #bfdbfe;
}

/* --------------------------------------------------------------------------
   7. WORKSPACE 4: EVALUATOR (StateAlgebraTree.tsx)
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

.rank-num-badge {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--text-dim);
}

.rank-title {
  font-size: 0.95rem;
  font-weight: 800;
  color: #ffffff;
}

.rank-desc {
  font-size: 0.72rem;
  color: var(--text-dim);
}

.operator-buttons-group {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

@media (max-width: 768px) {
  .operator-buttons-group {
    grid-template-columns: 1fr;
  }
}

.op-btn {
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

.op-btn:hover {
  background: #111a28;
  border-color: rgba(255, 255, 255, 0.2);
}

.op-btn.is-active-op {
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

.op-sub {
  font-size: 0.72rem;
  color: var(--text-dim);
  line-height: 1.35;
}

.k-threshold-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.k-picker-label {
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.k-btn {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 4px 10px;
  font-size: 0.72rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  cursor: pointer;
}

.k-btn.is-selected-k {
  border-color: var(--f1-blue);
  color: #ffffff;
  background: #1e293b;
  font-weight: 700;
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

.role-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.role-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.role-name {
  font-size: 0.82rem;
  font-weight: 700;
  color: #ffffff;
}

.role-id {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
}

.role-desc {
  font-size: 0.7rem;
  color: var(--text-dim);
  line-height: 1.3;
}

.role-selectors-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px;
}

.role-select-chip {
  background: #0b0f17;
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 6px;
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.12s ease;
  text-align: center;
}

.role-select-chip:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ffffff;
}

.role-select-chip.is-active {
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

.result-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-operation-name {
  font-size: 1.05rem;
  font-weight: 800;
  color: #ffffff;
}

.formal-soundness-badge {
  font-size: 0.68rem;
  font-family: var(--font-mono);
  color: #34d399;
  background: rgba(16, 185, 129, 0.1);
  padding: 4px 8px;
  border-radius: 4px;
}

.result-card-body {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
}

.result-verdict-large {
  display: flex;
  align-items: center;
}

.result-card-footer {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rule-box {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.rule-name {
  font-size: 0.75rem;
  color: #cbd5e1;
}

.trace-box {
  background: #090d14;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.trace-label {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-dim);
  text-transform: uppercase;
}

.trace-code {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: #34d399;
  font-weight: 700;
}
"""

styles_path = Path(r"e:\Caliberv2\frontend\src\styles.css")
content = styles_path.read_text(encoding="utf-8")

start_marker = "/* ==========================================================================\n   PULSE REDESIGN CORRECTION — INTEGRITY BOARD & SIA LOGIC LAB WORKBENCH\n   ========================================================================== */"
end_marker = "/* --- Agents & Pipeline View --- */"

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print(f"Error: Markers not found! start_idx={start_idx}, end_idx={end_idx}")
    exit(1)

updated_content = content[:start_idx] + exact_css + "\n\n" + content[end_idx:]
styles_path.write_text(updated_content, encoding="utf-8")
print(f"Successfully injected exact CSS! New length: {len(updated_content)}")
