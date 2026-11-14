import React from 'react';
import type { DecisionDisposition, IntegrityState } from '../../types/calibre';
import { AlertTriangleIcon, CheckCircleIcon, CircleDotIcon, ShieldIcon } from '../icons';

interface StateBadgeProps {
  state: IntegrityState | null | undefined;
  disposition?: DecisionDisposition;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
  tooltip?: string;
}

export const StateBadge: React.FC<StateBadgeProps> = ({
  state = 'UNKNOWN',
  disposition = 'NORMAL',
  size = 'md',
  showLabel = true,
  className = '',
  tooltip,
}) => {
  // If disposition is VOIDED, render administrative disposition badge
  if (disposition === 'VOIDED') {
    return (
      <span
        className={`state-badge state-badge--voided state-badge--${size} ${className}`}
        title={tooltip || 'Decision disposition: VOIDED (Legitimate absence, excluded from failure count)'}
      >
        <span className="state-badge__icon-dash">⊘</span>
        {showLabel && <span className="state-badge__label">VOIDED</span>}
      </span>
    );
  }

  const effectiveState: IntegrityState = state || 'UNKNOWN';

  const renderIcon = () => {
    switch (effectiveState) {
      case 'HEALTHY':
        return <ShieldIcon size={size === 'sm' ? 12 : 14} className="state-badge__icon" />;
      case 'SUSPECT':
        return <AlertTriangleIcon size={size === 'sm' ? 12 : 14} className="state-badge__icon" />;
      case 'UNKNOWN':
        return <CircleDotIcon size={size === 'sm' ? 12 : 14} className="state-badge__icon" />;
      case 'DEGRADED':
        return (
          <svg width={size === 'sm' ? 12 : 14} height={size === 'sm' ? 12 : 14} viewBox="0 0 24 24" fill="currentColor" className="state-badge__icon">
            <path d="M12 2L1 21h22L12 2z" />
          </svg>
        );
    }
  };

  const defaultTooltip = {
    HEALTHY: 'HEALTHY: Mandatory requirements satisfied under declared assumptions',
    SUSPECT: 'SUSPECT: Evidence anomaly, uncorroborated single source, or stale reference',
    UNKNOWN: 'UNKNOWN: Evidence slot pending, unobserved, or awaiting clock tick',
    DEGRADED: 'DEGRADED: Constraint breach, physical bounds violated, or checksum failure',
  }[effectiveState];

  return (
    <span
      className={`state-badge state-badge--${effectiveState.toLowerCase()} state-badge--${size} ${className}`}
      title={tooltip || defaultTooltip}
    >
      {renderIcon()}
      {showLabel && <span className="state-badge__label">{effectiveState}</span>}
    </span>
  );
};

