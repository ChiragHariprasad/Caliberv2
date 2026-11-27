import React from 'react';

interface ThresholdMarginGaugeProps {
  measuredValue: number;
  thresholdValue: number;
  uncertainty: number; // e.g. 0.11 km/h
  unit?: string;
  label?: string;
  className?: string;
}

export const ThresholdMarginGauge: React.FC<ThresholdMarginGaugeProps> = ({
  measuredValue,
  thresholdValue,
  uncertainty,
  unit = 'km/h',
  label = 'Pit Lane Speed Enforcement (Pattern P3)',
  className = '',
}) => {
  const margin = measuredValue - thresholdValue;
  const isExceeded = margin > 0;
  const isWithinUncertainty = isExceeded && margin <= uncertainty;

  // Window range for visual gauge: threshold +/- 3 * uncertainty (or at least +/- 1.0)
  const rangeSpan = Math.max(1.0, uncertainty * 3);
  const minVal = thresholdValue - rangeSpan;
  const maxVal = thresholdValue + rangeSpan;

  const toPercent = (v: number) => {
    return Math.max(0, Math.min(100, ((v - minVal) / (maxVal - minVal)) * 100));
  };

  const thresholdPct = toPercent(thresholdValue);
  const bandLoPct = toPercent(thresholdValue - uncertainty);
  const bandHiPct = toPercent(thresholdValue + uncertainty);
  const measuredPct = toPercent(measuredValue);

  return (
    <div className={`threshold-margin-card ${className}`}>
      <div className="threshold-margin__header">
        <span className="threshold-margin__title">{label}</span>
        <span
          className={`threshold-margin__status-tag ${
            !isExceeded
              ? 'status--compliant'
              : isWithinUncertainty
              ? 'status--within-uncertainty'
              : 'status--exceeded'
          }`}
        >
          {!isExceeded
            ? 'COMPLIANT'
            : isWithinUncertainty
            ? 'WITHIN UNCERTAINTY (POLICY DISCRETION)'
            : 'DEFINITIVE EXCEEDANCE'}
        </span>
      </div>

      {/* Visual Gauge Axis */}
      <div className="threshold-gauge-track">
        {/* Safe compliant zone */}
        <div className="gauge-zone zone--safe" style={{ left: '0%', width: `${thresholdPct}%` }} />
        {/* Guard band zone (+/- uncertainty) */}
        <div
          className="gauge-zone zone--uncertainty"
          style={{ left: `${bandLoPct}%`, width: `${bandHiPct - bandLoPct}%` }}
          title={`Guard Band: ±${uncertainty.toFixed(2)} ${unit}`}
        />
        {/* Breach zone */}
        <div
          className="gauge-zone zone--breach"
          style={{ left: `${thresholdPct}%`, width: `${100 - thresholdPct}%` }}
        />

        {/* Threshold Benchmark Tick */}
        <div className="gauge-marker marker--threshold" style={{ left: `${thresholdPct}%` }}>
          <span className="marker-line" />
          <span className="marker-label">Limit: {thresholdValue.toFixed(2)} {unit}</span>
        </div>

        {/* Measured Value Needle */}
        <div className="gauge-marker marker--measured" style={{ left: `${measuredPct}%` }}>
          <span className="needle-dot" />
          <span className="needle-label">
            Observed: {measuredValue.toFixed(2)} {unit}
          </span>
        </div>
      </div>

      {/* Detail Metrics Footer */}
      <div className="threshold-margin__metrics">
        <div className="t-metric">
          <span className="t-label">MEASUREMENT</span>
          <strong className="t-val">{measuredValue.toFixed(2)} {unit}</strong>
        </div>
        <div className="t-metric">
          <span className="t-label">REGULATORY LIMIT</span>
          <strong className="t-val">{thresholdValue.toFixed(2)} {unit}</strong>
        </div>
        <div className="t-metric">
          <span className="t-label">NET MARGIN</span>
          <strong className={`t-val ${margin > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {margin > 0 ? `+${margin.toFixed(3)}` : margin.toFixed(3)} {unit}
          </strong>
        </div>
        <div className="t-metric">
          <span className="t-label">GUARD BAND UNCERTAINTY</span>
          <strong className="t-val">±{uncertainty.toFixed(3)} {unit}</strong>
        </div>
      </div>
    </div>
  );
};

