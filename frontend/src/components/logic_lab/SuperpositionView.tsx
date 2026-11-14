import React from 'react';
import type { IntegrityState, ResolutionMaturity } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';

interface SuperpositionViewProps {
  decisionId?: string;
  contractId?: string;
  lowerBound: IntegrityState;
  upperBound: IntegrityState;
  currentState: IntegrityState;
  maturity: ResolutionMaturity;
  openSlots?: Array<{ roleId: string; status: 'ADMITTED' | 'PENDING' | 'EXPIRED' }>;
  className?: string;
}

const LATTICE_ORDER: IntegrityState[] = ['DEGRADED', 'UNKNOWN', 'SUSPECT', 'HEALTHY'];

export const SuperpositionView: React.FC<SuperpositionViewProps> = ({
  decisionId = 'dec-pit-speed-d16-l24',
  contractId = 'pit_speed v1.0.0',
  lowerBound = 'SUSPECT',
  upperBound = 'HEALTHY',
  currentState = 'SUSPECT',
  maturity = 'OPEN',
  openSlots = [
    { roleId: 'timing_speed', status: 'ADMITTED' },
    { roleId: 'configured_distance', status: 'ADMITTED' },
    { roleId: 'vehicle_speed', status: 'PENDING' },
  ],
  className = '',
}) => {
  const isStateResolved = lowerBound === upperBound || maturity === 'STATE_RESOLVED';
  const isTupleResolved = maturity === 'TUPLE_RESOLVED';

  const loIdx = LATTICE_ORDER.indexOf(lowerBound);
  const hiIdx = LATTICE_ORDER.indexOf(upperBound);

  return (
    <div className={`superposition-card panel ${className}`}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Quantum-Inspired Possible-World Logic</p>
          <h3>Possible-World Superposition & State Envelope</h3>
        </div>
        <div className="maturity-badge-group">
          <span className={`res-maturity-pill maturity--${maturity.toLowerCase()}`}>
            {maturity}
          </span>
          {isStateResolved && (
            <span className="state-resolved-chip">BOUNDS CONVERGED</span>
          )}
        </div>
      </div>

      <div className="superposition-body">
        <div className="instance-meta-bar">
          <span>Decision: <code>{decisionId}</code></span>
          <span>Contract: <strong>{contractId}</strong></span>
          <span>Maturity: <strong>{maturity}</strong></span>
        </div>

        {/* Envelope Axis Visualization */}
        <div className="envelope-visual-container">
          <span className="envelope-axis-label">Four-State Algebraic Lattice Order:</span>

          <div className="envelope-track">
            {LATTICE_ORDER.map((st, idx) => {
              const inEnvelope = idx >= loIdx && idx <= hiIdx;
              const isCurrent = st === currentState;

              return (
                <div
                  key={st}
                  className={`envelope-step ${inEnvelope ? 'is-inside-envelope' : 'is-outside'} ${
                    isCurrent ? 'is-current-point' : ''
                  }`}
                >
                  <span className="step-point" />
                  <span className="step-name">{st}</span>
                  {st === lowerBound && <span className="bound-tag lo-tag">Lower Bound</span>}
                  {st === upperBound && st !== lowerBound && <span className="bound-tag hi-tag">Upper Bound</span>}
                  {isCurrent && <span className="current-marker">[CURRENT]</span>}
                </div>
              );
            })}
          </div>

          <div className="envelope-bracket-summary">
            <span>
              Envelope Range: <strong>[{lowerBound} -&gt; {upperBound}]</strong>
            </span>
            <span className="envelope-explainer">
              {isStateResolved
                ? '[RESOLVED] Bounds have converged; pending evidence cannot change the outcome.'
                : 'Pending evidence slots may still alter the final verdict state within this envelope.'}
            </span>
          </div>
        </div>

        {/* Pending / Admitted Evidence Slots */}
        <div className="evidence-slots-container">
          <h4>Evidence Role Slots Lifecycle</h4>
          <div className="slots-grid">
            {openSlots.map((slot) => (
              <div key={slot.roleId} className={`slot-card slot--${slot.status.toLowerCase()}`}>
                <div className="slot-header">
                  <span className="slot-role-name"><code>{slot.roleId}</code></span>
                  <span className={`slot-status-tag status--${slot.status.toLowerCase()}`}>
                    {slot.status === 'ADMITTED' ? 'ADMITTED' : slot.status === 'PENDING' ? 'PENDING' : 'EXPIRED'}
                  </span>
                </div>
                <span className="slot-desc">
                  {slot.status === 'ADMITTED'
                    ? 'Valid observation admitted into ledger.'
                    : slot.status === 'PENDING'
                    ? 'Awaiting feed arrival before slot deadline.'
                    : 'Passed slot deadline; defaulted to UNKNOWN.'}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="superposition-notice">
          <span>
            * Note on Quantum-Inspired Logic: This models possible future states across pending evidence branches.
            It does NOT assign probabilistic weights and does NOT use quantum physical computation.
          </span>
        </div>
      </div>
    </div>
  );
};

