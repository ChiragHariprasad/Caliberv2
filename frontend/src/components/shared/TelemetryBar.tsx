import React from 'react';

interface TelemetryBarProps {
  label: string;
  value: number; // 0 to 100
  unit?: string;
  tone?: 'speed' | 'throttle' | 'brake' | 'neutral' | 'caution';
  className?: string;
  displayValue?: string | number;
}

export const TelemetryBar: React.FC<TelemetryBarProps> = ({
  label,
  value,
  unit = '%',
  tone = 'throttle',
  className = '',
  displayValue,
}) => {
  const clamped = Math.max(0, Math.min(100, isNaN(value) ? 0 : value));

  return (
    <div className={`telemetry-bar-card telemetry-bar-card--${tone} ${className}`}>
      <div className="telemetry-bar__header">
        <span className="telemetry-bar__label">{label}</span>
        <span className="telemetry-bar__value">
          {displayValue !== undefined ? displayValue : `${Math.round(clamped)}${unit}`}
        </span>
      </div>
      <div className="telemetry-bar__track">
        <div
          className="telemetry-bar__fill"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
};

