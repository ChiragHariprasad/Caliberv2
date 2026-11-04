import type { Assessment, Driver } from '../types';
import { CloseIcon } from './icons';

interface EvidenceDrawerProps {
  assessment: Assessment | null;
  driver?: Driver;
  onClose: () => void;
}

export function EvidenceDrawer({ assessment, driver, onClose }: EvidenceDrawerProps) {
  if (!assessment) return null;

  const team = driver?.team ?? 'Ferrari';
  const driverName = driver?.name ?? `Driver #${assessment.driverNumber}`;

  return (
    <div className="evidence-drawer-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="evidence-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <span className="drawer-eyebrow">AI Tactical Intelligence Briefing</span>
            <h2 className="drawer-title">{assessment.title}</h2>
            <div className="drawer-driver-tag">
              <span>{driverName}</span>
              <span className="dot-sep">•</span>
              <span>{team}</span>
              <span className="dot-sep">•</span>
              <span className="drawer-version-tag">Revision {assessment.version ?? 2}</span>
            </div>
          </div>
          <button type="button" className="drawer-close-btn" onClick={onClose} aria-label="Close drawer">
            <CloseIcon size={16} />
          </button>
        </div>

        <div className="drawer-body">
          {/* Core Reasoning */}
          <div className="drawer-section">
            <h4 className="section-title">Tactical Rationale</h4>
            <p className="section-text">{assessment.narrative}</p>
          </div>

          {/* Forecast & Alternatives */}
          <div className="drawer-section drawer-forecast-box">
            <div className="forecast-item">
              <span className="item-label">Predicted 1–2 Lap Horizon</span>
              <span className="item-value">{assessment.forecast}</span>
            </div>
            <div className="forecast-item">
              <span className="item-label">Tactical Counter-Factual</span>
              <span className="item-value alternative-text">{assessment.alternative}</span>
            </div>
          </div>

          {/* Model Synthesis & Calibration State */}
          <div className="drawer-section">
            <h4 className="section-title">Certainty Calibration & Methodology</h4>
            <div className="confidence-meter-card">
              <div className="meter-left">
                <span className="meter-score">{assessment.calibrationStatus ?? 'DETERMINISTIC HEURISTIC'}</span>
                <span className="meter-sub">Uncalibrated · Strictly zero hallucinated probability</span>
              </div>
              <div className="meter-right">
                <span className="provenance-pill">Agent 5 Consequence Fusion</span>
                <span className="provenance-sub">Synthesized across Agents 1–4 event streams</span>
              </div>
            </div>
          </div>

          {/* Evidence trail */}
          <div className="drawer-section">
            <h4 className="section-title">Referenced Evidence Trail</h4>
            <ul className="evidence-list">
              {assessment.evidence.map((ref, idx) => (
                <li key={idx} className="evidence-item">
                  <span className="evidence-hash-icon">#</span>
                  <code>{ref}</code>
                </li>
              ))}
            </ul>
          </div>

          {/* Data Coverage Matrix */}
          <div className="drawer-section">
            <h4 className="section-title">Multi-Domain Stream Coverage</h4>
            <div className="coverage-matrix-grid">
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Race Control</span>
                <span className="cell-state">COMPLETE (Agent 1)</span>
              </div>
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Track State</span>
                <span className="cell-state">COMPLETE (Agent 2)</span>
              </div>
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Vehicle Response</span>
                <span className="cell-state">COMPLETE (Agent 3)</span>
              </div>
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Tyre Strategy</span>
                <span className="cell-state">COMPLETE (Agent 4)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
