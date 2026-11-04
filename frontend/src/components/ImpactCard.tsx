import type { Assessment, Driver } from '../types';

interface ImpactCardProps {
  assessment: Assessment;
  driver?: Driver;
  onEvidence: (assessment: Assessment) => void;
}

export function ImpactCard({ assessment, driver, onEvidence }: ImpactCardProps) {
  const initials = driver?.initials ?? String(assessment.driverNumber);
  const team = driver?.team ?? 'Formula 1';

  return (
    <article className={`impact-card impact-card--${assessment.impact}`}>
      <div className="impact-card__topline">
        <div className="driver-chip">
          <span className="driver-chip__initials">{initials}</span>
          <div>
            <strong>{driver?.name ?? `Driver #${assessment.driverNumber}`}</strong>
            <small className="driver-chip__team">{team}</small>
          </div>
        </div>
        <div className="impact-card__badges">
          {assessment.version && (
            <span className="version-pill">REV v{assessment.version}</span>
          )}
          {assessment.confidence !== null && assessment.confidence !== undefined ? (
            <span
              className="confidence-ring"
              title={`Model confidence: ${assessment.confidence}%`}
              style={{ '--confidence': `${assessment.confidence * 3.6}deg` } as React.CSSProperties}
            >
              {assessment.confidence}%
            </span>
          ) : (
            <span className="uncalibrated-chip" title="Model outputs deterministic heuristic, not calibrated probability">
              HEURISTIC
            </span>
          )}
        </div>
      </div>

      <h3 className="impact-card__headline">{assessment.title}</h3>
      <p className="impact-card__narrative">{assessment.narrative}</p>

      {assessment.driverRadio && (
        <div className="radio-transmission">
          <div className="radio-header">
            <span className="radio-wave-icon">📻</span>
            <span>TEAM RADIO INTERCEPT</span>
          </div>
          <p className="radio-body">"{assessment.driverRadio.replace(/^Team Radio Transmission:\s*"?|"?$/g, '')}"</p>
        </div>
      )}

      <div className="impact-card__forecast">
        <span className="forecast-icon">✦</span>
        <span>{assessment.forecast}</span>
      </div>

      <div className="impact-card__footer">
        <div className="footer-status-group">
          <span className={`finding-state finding-state--${assessment.status.toLowerCase()}`}>
            {assessment.status}
          </span>
          {assessment.supersedesId && (
            <span className="superseded-badge" title={`Supersedes ${assessment.supersedesId}`}>
              Supersedes v1
            </span>
          )}
        </div>
        <button
          type="button"
          className="evidence-trigger-btn"
          onClick={() => onEvidence(assessment)}
        >
          <span>Why this?</span>
          <span className="btn-arrow">→</span>
        </button>
      </div>
    </article>
  );
}
