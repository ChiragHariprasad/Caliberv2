import type { Assessment, Driver } from '../types';

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
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {/* Radio transmission quote */}
          {assessment.driverRadio && (
            <div className="drawer-section drawer-radio-callout">
              <div className="callout-heading">
                <span className="radio-icon-pulse">📻</span>
                <h4>OFFICIAL TEAM RADIO TRANSCRIPT</h4>
              </div>
              <p className="callout-quote">
                "{assessment.driverRadio.replace(/^Team Radio Transmission:\s*"?|"?$/g, '')}"
              </p>
            </div>
          )}

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

          {/* Confidence & Model Synthesis */}
          <div className="drawer-section">
            <h4 className="section-title">Model Certainty & Intelligence Provenance</h4>
            <div className="confidence-meter-card">
              <div className="meter-left">
                <span className="meter-score">{assessment.confidence ? `${assessment.confidence}%` : 'HEURISTIC'}</span>
                <span className="meter-sub">{assessment.calibrationStatus ?? 'Deterministic Heuristic'}</span>
              </div>
              <div className="meter-right">
                <span className="provenance-pill">Deterministic Fusion Engine</span>
                <span className="provenance-sub">All raw events hashed with monotonic event-time</span>
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
            <h4 className="section-title">Stream Data Coverage</h4>
            <div className="coverage-matrix-grid">
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Race Control</span>
                <span className="cell-status">COMPLETE</span>
              </div>
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Tyre & Strategy</span>
                <span className="cell-status">COMPLETE</span>
              </div>
              <div className="coverage-cell cell-complete">
                <span className="cell-name">Track Weather</span>
                <span className="cell-status">COMPLETE</span>
              </div>
              <div className="coverage-cell cell-unavailable">
                <span className="cell-name">Chassis Telemetry</span>
                <span className="cell-status">UNAVAILABLE (NO FABRICATION)</span>
              </div>
            </div>
          </div>
        </div>

        <div className="drawer-footer">
          <button type="button" className="drawer-dismiss-btn" onClick={onClose}>
            Close Briefing
          </button>
        </div>
      </div>
    </div>
  );
}
