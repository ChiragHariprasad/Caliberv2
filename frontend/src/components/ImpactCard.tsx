import type { Assessment, Driver } from '../types';
import { SparkleIcon } from './icons';

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
          <span className="uncalibrated-chip" title="Model outputs deterministic heuristic, not calibrated probability">
            {assessment.calibrationStatus ?? 'DETERMINISTIC HEURISTIC'}
          </span>
        </div>
      </div>

      <h3 className="impact-card__headline">{assessment.title}</h3>
      <p className="impact-card__narrative">{assessment.narrative}</p>

      <div className="impact-card__forecast">
        <SparkleIcon size={12} className="forecast-icon text-amber-400" />
        <span>{assessment.forecast}</span>
      </div>

      <div className="impact-card__footer">
        <div className="footer-status-group">
          <span className={`finding-state finding-state--${assessment.status.toLowerCase()}`}>
            {assessment.status}
          </span>
          {assessment.supersedesId && (
            <span className="superseded-badge" title={`Supersedes ${assessment.supersedesId}`}>
              Supersedes {assessment.supersedesId}
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
