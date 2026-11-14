import React from 'react';

export type DataRegime = 'PUBLIC' | 'LICENSED' | 'INSTITUTIONAL' | 'LAB';

interface RegimePillProps {
  regime?: DataRegime | string;
  className?: string;
  showWarning?: boolean;
}

export const RegimePill: React.FC<RegimePillProps> = ({
  regime = 'PUBLIC',
  className = '',
  showWarning = true,
}) => {
  const norm = (regime || 'PUBLIC').toUpperCase() as DataRegime;

  const labels: Record<DataRegime, string> = {
    PUBLIC: 'PUBLIC REGIME',
    LICENSED: 'LICENSED REGIME',
    INSTITUTIONAL: 'INSTITUTIONAL REGIME',
    LAB: 'LAB / SYNTHETIC',
  };

  const tooltips: Record<DataRegime, string> = {
    PUBLIC:
      'PUBLIC REGIME: Open/public data sharing common upstream platform. Maximum Corroboration Depth: 1. Disjoint multi-source independence cannot be proven.',
    LICENSED:
      'LICENSED REGIME: Authenticated provider feeds with declared SLAs and timing loop calibration certificates.',
    INSTITUTIONAL:
      'INSTITUTIONAL REGIME: Multiple independent hardware taps, telemetry loggers, and survey baselines. Multi-source corroboration depth verified.',
    LAB:
      'LAB / SYNTHETIC: Injected faults, counterfactual scenarios, and simulated physics models. Watermarked for testing only.',
  };

  return (
    <span
      className={`regime-pill regime-pill--${norm.toLowerCase()} ${className}`}
      title={tooltips[norm] || tooltips.PUBLIC}
    >
      <span className="regime-pill__dot" />
      <span className="regime-pill__name">{labels[norm] || norm}</span>
      {norm === 'PUBLIC' && showWarning && (
        <span className="regime-pill__badge" title="Common-cause exposure active (Depth: 1)">
          COMMON-CAUSE EXP
        </span>
      )}
    </span>
  );
};

