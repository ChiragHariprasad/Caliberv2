import React from 'react';

export type DataRegime = 'PUBLIC' | 'LICENSED' | 'INSTITUTIONAL' | 'LAB' | 'SYNTHETIC' | 'PREVIEW';

interface RegimePillProps {
  regime?: DataRegime | string;
  className?: string;
  showWarning?: boolean;
}

export const RegimePill: React.FC<RegimePillProps> = ({
  regime = 'SYNTHETIC',
  className = '',
  showWarning = true,
}) => {
  const norm = (regime || 'SYNTHETIC').toUpperCase() as DataRegime;

  const labels: Record<DataRegime, string> = {
    PUBLIC: 'PUBLIC REGIME',
    LICENSED: 'LICENSED REGIME',
    INSTITUTIONAL: 'INSTITUTIONAL REGIME',
    LAB: 'LAB ARCHIVE',
    SYNTHETIC: 'SYNTHETIC SIM',
    PREVIEW: 'GEOMETRY PREVIEW',
  };

  const tooltips: Record<DataRegime, string> = {
    PUBLIC:
      'PUBLIC REGIME: Open/public data sharing common upstream platform. Maximum Corroboration Depth: 1. Disjoint multi-source independence cannot be proven.',
    LICENSED:
      'LICENSED REGIME: Authenticated provider feeds with declared SLAs and timing loop calibration certificates.',
    INSTITUTIONAL:
      'INSTITUTIONAL REGIME: Multiple independent hardware taps, telemetry loggers, and survey baselines. Multi-source corroboration depth verified.',
    LAB:
      'LAB ARCHIVE: Derived/windowed replay capture combining open archive records with synthetic high-rate streams. Not institutional FIA feed.',
    SYNTHETIC:
      'SYNTHETIC SIM: Deterministic synthetic simulator stream generated locally for verification and testing.',
    PREVIEW:
      'GEOMETRY PREVIEW: Verified circuit geometry catalogue only; no timing or telemetry capture loaded.',
  };

  const styleKey = norm === 'SYNTHETIC' || norm === 'PREVIEW' ? 'lab' : norm.toLowerCase();

  return (
    <span
      className={`regime-pill regime-pill--${styleKey} ${className}`}
      title={tooltips[norm] || tooltips.SYNTHETIC}
    >
      <span className="regime-pill__dot" />
      <span className="regime-pill__name">{labels[norm] || norm}</span>
      {(norm === 'PUBLIC' || norm === 'LAB' || norm === 'SYNTHETIC') && showWarning && (
        <span className="regime-pill__badge" title="Single upstream source or simulated feed — independent institutional corroboration absent">
          {norm === 'SYNTHETIC' ? 'SIMULATED DATA' : 'COMMON-CAUSE EXP'}
        </span>
      )}
    </span>
  );
};

