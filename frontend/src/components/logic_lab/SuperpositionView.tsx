import React, { useMemo } from 'react';
import type { IntegrityState, ResolutionMaturity } from '../../types/calibre';
import { StateBadge } from '../shared/StateBadge';
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, InfoIcon, ShieldIcon } from '../icons';

interface SuperpositionViewProps {
  decisionId?: string;
  contractId?: string;
  lowerBound?: IntegrityState;
  upperBound?: IntegrityState;
  currentState?: IntegrityState;
  maturity?: ResolutionMaturity;
  openSlots?: Array<{
    roleId: string;
    kind: 'evidence' | 'reference';
    status: 'ADMITTED' | 'PENDING' | 'MISSING' | 'REJECTED';
    value?: string | number;
    source: string;
    timestamp: string;
    isLimiting: boolean;
  }>;
  availableDecisions?: string[];
  onSelectDecision?: (decisionId: string) => void;
  className?: string;
}

const ORDERED_LATTICE = [
  {
    state: 'DEGRADED' as IntegrityState,
    rank: 0,
    color: '#ff4d4f',
    meaning: 'Irrevocable Failure / Bound Breach',
    conditions: 'Admitted defect witness, physical limit breach, or invalid signature.',
  },
  {
    state: 'UNKNOWN' as IntegrityState,
    rank: 1,
    color: '#64748b',
    meaning: 'Epistemic Absence / Pending Ingestion',
    conditions: 'Required evidence slot has zero admitted atoms and cutoff not yet reached.',
  },
  {
    state: 'SUSPECT' as IntegrityState,
    rank: 2,
    color: '#ffd000',
    meaning: 'Plausible Anomaly / Corroboration Void',
    conditions: 'Evidence present but uncorroborated single-source or clock skew detected.',
  },
  {
    state: 'HEALTHY' as IntegrityState,
    rank: 3,
    color: '#00ff88',
    meaning: 'Fully Verified Invariant Satisfaction',
    conditions: 'All required constraints evaluated true across independent admitted origins.',
  },
];

export const SuperpositionView: React.FC<SuperpositionViewProps> = ({
  decisionId = 'dec-pit_speed-d16',
  contractId = 'pit_speed v1.0.0',
  lowerBound = 'UNKNOWN',
  upperBound = 'HEALTHY',
  currentState = 'UNKNOWN',
  maturity = 'OPEN',
  openSlots,
  availableDecisions = [],
  onSelectDecision,
  className = '',
}) => {
  // Default evidence slots if not provided
  const slots = useMemo(() => {
    if (openSlots && openSlots.length > 0) return openSlots;
    return [
      {
        roleId: 'vehicle_speed',
        kind: 'evidence' as const,
        status: 'ADMITTED' as const,
        value: '79.2 km/h',
        source: 'FOM_OPTICAL_LOOP',
        timestamp: '12:04:15.240',
        isLimiting: false,
      },
      {
        roleId: 'timing_speed',
        kind: 'evidence' as const,
        status: 'ADMITTED' as const,
        value: '78.8 km/h',
        source: 'CAN_BUS_GATEWAY',
        timestamp: '12:04:15.238',
        isLimiting: false,
      },
      {
        roleId: 'configured_distance',
        kind: 'evidence' as const,
        status: 'PENDING' as const,
        value: '—',
        source: 'TRACK_MAP_CALIBRATION',
        timestamp: 'Awaiting Gate G02 Tick',
        isLimiting: true,
      },
      {
        roleId: 'track_geometry',
        kind: 'reference' as const,
        status: 'ADMITTED' as const,
        value: 'Gate G02 Validated',
        source: 'FIA_GEOMETRY_SPEC',
        timestamp: 'Pre-session static',
        isLimiting: false,
      },
      {
        roleId: 'calibration_bias',
        kind: 'reference' as const,
        status: 'PENDING' as const,
        value: '—',
        source: 'TELEMETRY_CLOCK_MASTER',
        timestamp: 'Awaiting monotonic tick',
        isLimiting: true,
      },
    ];
  }, [openSlots]);

  const loIdx = ORDERED_LATTICE.findIndex((l) => l.state === lowerBound);
  const hiIdx = ORDERED_LATTICE.findIndex((l) => l.state === upperBound);
  const curIdx = ORDERED_LATTICE.findIndex((l) => l.state === currentState);

  const isResolved = lowerBound === upperBound || maturity === 'STATE_RESOLVED';

  return (
    <div className={`state-envelope-workspace ${className}`}>
      {/* 1. Top Section: Visual State Lattice & Possible-World Envelope */}
      <section className="envelope-visual-section">
        <div className="section-title-wrap">
          <div className="title-left">
            <span className="eyebrow-accent">TOTAL ORDER ALGEBRA</span>
            <h2 className="workspace-section-title">Four-State Algebraic Lattice &amp; Envelope</h2>
          </div>
          <div className="title-right">
            <span className="lattice-order-formula">
              <code>DEGRADED (0) &lt; UNKNOWN (1) &lt; SUSPECT (2) &lt; HEALTHY (3)</code>
            </span>
          </div>
        </div>

        {/* 4-State Progression Grid */}
        <div className="lattice-nodes-grid">
          {ORDERED_LATTICE.map((node, idx) => {
            const isCurrent = node.state === currentState;
            const isLower = node.state === lowerBound;
            const isUpper = node.state === upperBound;
            const inRange = idx >= loIdx && idx <= hiIdx;

            return (
              <div
                key={node.state}
                className={`lattice-state-card ${isCurrent ? 'is-current-state' : ''} ${
                  inRange ? 'is-in-envelope-range' : 'is-outside-range'
                }`}
              >
                <div className="state-card-header">
                  <div className="state-card-rank-badge" style={{ borderColor: node.color }}>
                    RANK {node.rank}
                  </div>
                  <StateBadge state={node.state} size="sm" />
                </div>

                <div className="state-card-body">
                  <strong className="state-name-display" style={{ color: node.color }}>
                    {node.state}
                  </strong>
                  <p className="state-meaning-text">{node.meaning}</p>
                  <div className="state-conditions-box">
                    <span className="cond-label">TRIGGER CONDITIONS:</span>
                    <p className="cond-text">{node.conditions}</p>
                  </div>
                </div>

                {/* Range Indicators */}
                <div className="state-card-envelope-tags">
                  {isCurrent && <span className="envelope-tag tag--current">CURRENT STATE</span>}
                  {isLower && <span className="envelope-tag tag--lower">LOWER BOUND</span>}
                  {isUpper && <span className="envelope-tag tag--upper">UPPER BOUND</span>}
                  {inRange && !isLower && !isUpper && !isCurrent && (
                    <span className="envelope-tag tag--possible">POSSIBLE OUTCOME</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Interval Bar Indicator */}
        <div className="envelope-range-bar-wrapper">
          <div className="range-bar-legend">
            <span className="range-label">
              Active Evaluation Envelope: <strong>[{lowerBound} &rarr; {upperBound}]</strong>
            </span>
            <span className="range-status">
              {isResolved ? (
                <span className="text-emerald-400">
                  <CheckCircleIcon size={13} className="inline mr-1" />
                  State Resolved (Bounds Converged)
                </span>
              ) : (
                <span className="text-cyan-400">
                  <ClockIcon size={13} className="inline mr-1" />
                  Superposition Open (Pending {slots.filter((s) => s.isLimiting).length} Evidence Slots)
                </span>
              )}
            </span>
          </div>

          <div className="range-bar-track">
            <div
              className="range-bar-fill"
              style={{
                left: `${(loIdx / 3) * 100}%`,
                width: `${((hiIdx - loIdx) / 3) * 100}%`,
              }}
            />
            {ORDERED_LATTICE.map((n, i) => (
              <div
                key={n.state}
                className={`range-bar-tick ${i === curIdx ? 'is-current-tick' : ''}`}
                style={{ left: `${(i / 3) * 100}%` }}
              >
                <div className="tick-dot" style={{ backgroundColor: n.color }} />
                <span className="tick-name">{n.state}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 2. Middle Section: Two-Column Workbench Layout */}
      <div className="envelope-workbench-two-col">
        {/* Left Column: Evidence-Role Lifecycle */}
        <section className="envelope-roles-section">
          <div className="section-title-wrap">
            <div className="title-left">
              <span className="eyebrow-accent">EVIDENCE ADMISSION PIPELINE</span>
              <h3 className="workspace-section-title">Evidence-Role Lifecycle &amp; Limiting Children</h3>
            </div>
            <span className="role-count-pill">{slots.length} Participating Roles</span>
          </div>

          <div className="evidence-slots-table-wrap">
            <table className="evidence-slots-table">
              <thead>
                <tr>
                  <th>EVIDENCE ROLE</th>
                  <th>KIND</th>
                  <th>ADMISSION STATUS</th>
                  <th>OBSERVED VALUE</th>
                  <th>SOURCE ORIGIN</th>
                  <th>EVALUATOR IMPACT</th>
                </tr>
              </thead>
              <tbody>
                {slots.map((s) => (
                  <tr key={s.roleId} className={`slot-row ${s.isLimiting ? 'is-limiting-row' : ''}`}>
                    <td className="slot-role-cell">
                      <code>{s.roleId}</code>
                    </td>
                    <td>
                      <span className={`role-kind-pill ${s.kind === 'reference' ? 'is-ref' : 'is-ev'}`}>
                        {s.kind}
                      </span>
                    </td>
                    <td>
                      <span className={`slot-status-pill status--${s.status.toLowerCase()}`}>
                        {s.status}
                      </span>
                    </td>
                    <td className="font-mono text-slate-200">{s.value}</td>
                    <td className="text-xs text-slate-400">{s.source}</td>
                    <td>
                      {s.isLimiting ? (
                        <span className="limiting-impact-badge">
                          <AlertTriangleIcon size={12} className="inline mr-1 text-amber-400" />
                          Limiting Child
                        </span>
                      ) : (
                        <span className="resolved-impact-badge">
                          <CheckCircleIcon size={12} className="inline mr-1 text-emerald-400" />
                          Non-Limiting
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Right Column: Mathematical Explanation & Semantics */}
        <section className="envelope-explanation-section">
          <div className="section-title-wrap">
            <div className="title-left">
              <span className="eyebrow-accent">EPISTEMIC INTERPRETATION</span>
              <h3 className="workspace-section-title">Deterministic Reduction Semantics</h3>
            </div>
          </div>

          <div className="explanation-card-body">
            <div className="info-block">
              <div className="info-header">
                <InfoIcon size={14} className="text-cyan-400" />
                <strong>Monotonic Possibility Interval</strong>
              </div>
              <p>
                In SIA Core v3, before a decision reaches finality or tuple resolution, pending evidence roles are represented
                by an algebraic possibility envelope <code>[L, U]</code>. As knowledge time advances monotonically, newly
                admitted evidence atoms shrink this interval until L = U.
              </p>
            </div>

            <div className="info-block">
              <div className="info-header">
                <ShieldIcon size={14} className="text-purple-400" />
                <strong>Limiting Child Resolution</strong>
              </div>
              <p>
                A role is declared a <em>limiting child</em> if improving its integrity state would directly promote the
                lower bound of the contract. In the current configuration, observing <code>configured_distance</code> and{' '}
                <code>calibration_bias</code> will immediately resolve the decision from <strong>UNKNOWN</strong> to{' '}
                <strong>HEALTHY</strong>.
              </p>
            </div>

            <div className="info-block">
              <div className="info-header">
                <ClockIcon size={14} className="text-emerald-400" />
                <strong>Bitemporal Non-Interference</strong>
              </div>
              <p>
                All evidence evaluations are strictly indexed by Knowledge Time K. A late-arriving atom cannot retroactively
                alter historical decisions already sealed at earlier coordinates.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};
