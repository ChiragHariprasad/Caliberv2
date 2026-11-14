import React from 'react';
import { InfoIcon } from '../icons';

interface AssumptionsBarProps {
  surveyReference?: string;
  sensorToleranceMeters?: number;
  timingSource?: string;
  dataRegime?: string;
  className?: string;
}

export const AssumptionsBar: React.FC<AssumptionsBarProps> = ({
  surveyReference = 'Monaco-2025-v2.1 (Effective 2025-11-01 UTC)',
  sensorToleranceMeters = 0.05,
  timingSource = 'FOM Optical Loops & CAN Telemetry',
  dataRegime = 'PUBLIC',
  className = '',
}) => {
  return (
    <footer className={`assumptions-bar ${className}`} role="contentinfo">
      <div className="assumptions-bar__inner">
        <span className="assumptions-bar__tag">
          <InfoIcon size={12} className="assumptions-bar__icon" />
          <span>DECLARED BASELINE ASSUMPTIONS:</span>
        </span>
        <span className="assumptions-bar__item">
          <strong>Survey Baseline:</strong> <code>{surveyReference}</code>
        </span>
        <span className="assumptions-bar__sep">·</span>
        <span className="assumptions-bar__item">
          <strong>Uncertainty Guard Band:</strong> ±{sensorToleranceMeters}m (±{(sensorToleranceMeters * 100).toFixed(0)}cm)
        </span>
        <span className="assumptions-bar__sep">·</span>
        <span className="assumptions-bar__item">
          <strong>Timing Baseline:</strong> {timingSource}
        </span>
        <span className="assumptions-bar__sep">·</span>
        <span className="assumptions-bar__item">
          <strong>Regime Model:</strong> {dataRegime} (Corroboration evaluated per contract)
        </span>
      </div>
    </footer>
  );
};

