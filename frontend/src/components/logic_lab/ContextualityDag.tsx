import React from 'react';
import { StateBadge } from '../shared/StateBadge';

interface ContextualityDagProps {
  atomId?: string;
  roleId?: string;
  className?: string;
}

export const ContextualityDag: React.FC<ContextualityDagProps> = ({
  atomId = 'atm-spd-88f2',
  roleId = 'timing_speed',
  className = '',
}) => {
  return (
    <div className={`contextuality-dag-card panel ${className}`}>
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Epistemic Scope Locality</p>
          <h3>Contextuality Explorer (Cross-Contract Participation)</h3>
        </div>
        <span className="subtle-chip">One Atom · Many Independent Contracts</span>
      </div>

      <div className="contextuality-body">
        <div className="contextuality-summary">
          <p>
            Demonstrating how a single Evidence Atom (<code>{atomId}</code>, role: <code>{roleId}</code>) participates
            across multiple distinct decision contracts simultaneously without cross-contaminating orthogonal scopes.
          </p>
        </div>

        <div className="dag-flow-container">
          {/* Source Atom Node */}
          <div className="dag-atom-node">
            <span className="dag-node-type">ROOT EVIDENCE ATOM</span>
            <strong className="dag-atom-id">{atomId}</strong>
            <span className="dag-atom-role">role: {roleId} (60.08 km/h)</span>
          </div>

          <div className="dag-branch-lines">
            <div className="branch-arrow">&darr;</div>
            <div className="branch-arrow">&darr;</div>
            <div className="branch-arrow">&darr;</div>
          </div>

          {/* 3 Distinct Contract Outcomes */}
          <div className="dag-contracts-grid">
            <div className="contract-outcome-card">
              <div className="c-outcome-header">
                <span className="c-id">C01_lap_time_consistency</span>
                <StateBadge state="HEALTHY" size="sm" />
              </div>
              <p className="c-desc">
                Atom fulfills timing reference bounds. All constraints satisfied.
              </p>
              <span className="c-status-verdict">Outcome: HEALTHY</span>
            </div>

            <div className="contract-outcome-card is-suspect-outcome">
              <div className="c-outcome-header">
                <span className="c-id">C03_pit_speed_integrity</span>
                <StateBadge state="SUSPECT" size="sm" />
              </div>
              <p className="c-desc">
                Ratio against vehicle ECU speed is within uncertainty band of 60.00 km/h limit.
              </p>
              <span className="c-status-verdict text-amber-400">Outcome: SUSPECT</span>
            </div>

            <div className="contract-outcome-card">
              <div className="c-outcome-header">
                <span className="c-id">C05_telemetry_alignment</span>
                <StateBadge state="HEALTHY" size="sm" />
              </div>
              <p className="c-desc">
                Temporal alignment with lap-relative time class confirmed.
              </p>
              <span className="c-status-verdict">Outcome: HEALTHY</span>
            </div>
          </div>
        </div>

        <div className="contextuality-footer-note">
          <span>
            * Key Architectural Takeaway: A measurement anomaly in one contract (e.g. C03 pit speed) does NOT
            systemically invalidate or degrade unrelated decisions (e.g. C01 lap time) using the same observation.
          </span>
        </div>
      </div>
    </div>
  );
};

